#!/usr/bin/env python3
"""
Weekly SMART Report Generator for server health monitoring

This script:
  • Runs smartctl to fetch SMART health (overall and attribute details)
  • Extracts key metrics and compares against healthy benchmarks
  • Generates reports in CSV format
  • Supports email notifications for critical issues
  • Implements proper logging and error handling

Flow of the script:
1. Main execution starts at the bottom with main() function
2. Configuration is loaded from config.json
3. SmartReportGenerator instance is created
4. Report generation process:
   - Collects metrics from all disks in parallel
   - Generates CSV report
   - Checks for alerts
   - Sends email notifications if alerts are detected
"""

import subprocess
import re
import csv
import datetime
import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from concurrent.futures import ThreadPoolExecutor
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Configure logging system
# This sets up logging to both file and console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smart_report.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EmailConfig:
    """
    Class to hold email configuration settings
    Used to store SMTP server details and authentication information
    """
    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, 
                 app_password: str, use_tls: bool):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.app_password = app_password
        self.use_tls = use_tls

class Config:
    """
    Main configuration class that holds all settings for the script
    Loads and validates configuration from JSON file
    """
    def __init__(self, server_name: str, disks: List[str], output_dir: Path,
                 metric_map: Dict[str, str], healthy_benchmarks: Dict[str, str],
                 email_notification: bool, email_recipients: List[str],
                 email_config: EmailConfig, alert_thresholds: Dict[str, float]):
        self.server_name = server_name
        self.disks = disks
        self.output_dir = output_dir
        self.metric_map = metric_map
        self.healthy_benchmarks = healthy_benchmarks
        self.email_notification = email_notification
        self.email_recipients = email_recipients
        self.email_config = email_config
        self.alert_thresholds = alert_thresholds

    @classmethod
    def from_file(cls, config_path: str) -> 'Config':
        """
        Class method to load configuration from JSON file
        Args:
            config_path: Path to the configuration JSON file
        Returns:
            Config instance with all settings loaded
        """
        with open(config_path) as f:
            data = json.load(f)
        return cls(
            server_name=data['server_name'],
            disks=data['disks'],
            output_dir=Path(data['output_dir']),
            metric_map=data['metric_map'],
            healthy_benchmarks=data['healthy_benchmarks'],
            email_notification=data['email_notification'],
            email_recipients=data['email_recipients'],
            email_config=EmailConfig(**data['email_config']),
            alert_thresholds=data['alert_thresholds']
        )

class SmartReportGenerator:
    """
    Main class responsible for generating SMART reports
    Handles all operations from collecting metrics to sending alerts
    """
    def __init__(self, config: Config):
        """
        Initialize the report generator
        Args:
            config: Configuration object containing all settings
        """
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.alerts = []

    def parse_overall_health(self, disk: str) -> str:
        """
        Run 'smartctl -H' and return the overall health status string
        Args:
            disk: Disk device path
        Returns:
            Overall health status string
        """
        output = self.run_command(["sudo", "smartctl", "-H", disk])
        match = re.search(r"SMART overall-health self-assessment test result:\s*(.+)", output)
        return match.group(1).strip() if match else "Unknown"

    def parse_model(self, disk: str) -> Dict[str, str]:
        """
        Run 'smartctl -i' to get the device model, RPM, and capacity
        Args:
            disk: Disk device path
        Returns:
            Dictionary containing model, RPM, and capacity information
        """
        output = self.run_command(["sudo", "smartctl", "-i", disk])
        model_match = re.search(r"Device Model:\s*(.+)", output)
        rpm_match = re.search(r"Rotation Rate:\s*(\d+)\s*rpm", output)
        capacity_match = re.search(r"User Capacity:\s*\[(\d+\.?\d*)\s*[TGMK]B\]", output)
        
        # Convert capacity to GB
        capacity_gb = "N/A"
        if capacity_match:
            try:
                capacity = float(capacity_match.group(1))
                # Convert to GB based on unit
                if "TB" in output:
                    capacity_gb = f"{capacity * 1024:.2f}"
                elif "GB" in output:
                    capacity_gb = f"{capacity:.2f}"
                elif "MB" in output:
                    capacity_gb = f"{capacity / 1024:.2f}"
                elif "KB" in output:
                    capacity_gb = f"{capacity / (1024**2):.2f}"
            except ValueError:
                pass
        
        return {
            "Model": model_match.group(1).strip() if model_match else "Unknown",
            "RPM": rpm_match.group(1) if rpm_match else "N/A",
            "Capacity": capacity_gb
        }

    def parse_smart_attributes(self, disk: str) -> Dict[str, str]:
        """
        Run 'smartctl -A' and parse the SMART attribute lines
        Args:
            disk: Disk device path
        Returns:
            Dictionary mapping attribute IDs and names to their raw values
        """
        attributes = {}
        output = self.run_command(["sudo", "smartctl", "-A", disk])
        # Regex pattern to capture the SMART attribute fields
        pattern = re.compile(
            r"^\s*(\d+)\s+(\S+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+(?:\s+\S+)?\s+(.+)$"
        )
        for line in output.splitlines():
            m = pattern.match(line)
            if m:
                attr_id, attr_name, raw = m.groups()
                # In case raw value contains extra text, take the first token
                raw_val = raw.strip().split()[0]
                attributes[attr_id] = raw_val
                attributes[attr_name] = raw_val
        return attributes

    def run_command(self, cmd: List[str], retries: int = 3) -> str:
        """
        Execute a shell command with retry mechanism
        Args:
            cmd: List of command and arguments to execute
            retries: Number of retry attempts before giving up
        Returns:
            Command output as string
        Raises:
            subprocess.CalledProcessError: If command fails after all retries
        """
        for attempt in range(retries):
            try:
                result = subprocess.run(
                    cmd,
                    #(I've modified the run_command method to use the older style of capturing command output. The changes are:
                    # Replaced capture_output=True with explicit stdout=subprocess.PIPE and stderr=subprocess.PIPE
                    # Replaced text=True with universal_newlines=True (which is the older equivalent)
                    # These changes make the script compatible with Python 3.6 and older versions. The functionality remains exactly the same, but now it uses the older API that's available in all Python versions.)


                    # capture_output=True,
                    # text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    
                    check=True
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                if attempt == retries - 1:
                    logger.error(f"Command failed after {retries} attempts: {' '.join(cmd)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                continue

    def parse_time_value(self, time_str: str) -> float:
        """
        Parse time-based values like "53372h+48m+47.377s" into total hours
        Args:
            time_str: Time string in format "Xh+Ym+Zs"
        Returns:
            Total hours as float
        """
        try:
            hours = 0.0
            minutes = 0.0
            seconds = 0.0
            
            # Extract hours
            h_match = re.search(r'(\d+)h', time_str)
            if h_match:
                hours = float(h_match.group(1))
            
            # Extract minutes
            m_match = re.search(r'(\d+)m', time_str)
            if m_match:
                minutes = float(m_match.group(1))
            
            # Extract seconds
            s_match = re.search(r'(\d+\.?\d*)s', time_str)
            if s_match:
                seconds = float(s_match.group(1))
            
            return hours + (minutes / 60.0) + (seconds / 3600.0)
        except Exception as e:
            logger.warning(f"Failed to parse time value '{time_str}': {str(e)}")
            return 0.0

    def check_health_thresholds(self, disk: str, metrics: Dict[str, str]) -> List[str]:
        """
        Check if any metrics exceed configured alert thresholds
        Args:
            disk: Disk device path
            metrics: Dictionary of metric names and their values
        Returns:
            List of alert messages for exceeded thresholds
        """
        alerts = []
        for metric, value in metrics.items():
            if metric in self.config.alert_thresholds:
                try:
                    # Handle time-based values
                    if metric in ['Head_Flying_Hours', 'Power_On_Hours']:
                        value = self.parse_time_value(value)
                    else:
                        value = float(value)
                        
                    if value > self.config.alert_thresholds[metric]:
                        alerts.append(f"{disk} {metric}: {value} exceeds threshold "
                                   f"{self.config.alert_thresholds[metric]}")
                except ValueError:
                    logger.warning(f"Could not convert {value} to float for {metric}")
        return alerts

    def convert_lba_to_gb(self, lba_value: str) -> str:
        """
        Convert LBA (Logical Block Address) value to GB
        Args:
            lba_value: LBA value as string
        Returns:
            Value in GB as string with 2 decimal places
        """
        try:
            # LBA to GB conversion: 1 LBA = 512 bytes (standard sector size)
            lba = float(lba_value)
            gb = (lba * 512) / (1024**3)  # Convert bytes to GB
            return f"{gb:.2f}"
        except (ValueError, TypeError):
            return "N/A"

    def collect_disk_metrics(self, disk: str) -> Dict[str, str]:
        """
        Collect all SMART metrics for a specific disk
        Args:
            disk: Disk device path
        Returns:
            Dictionary of metric names and their values
        """
        try:
            metrics = {}
            # Collect basic disk information
            metrics["Overall SMART Health"] = self.parse_overall_health(disk)
            
            # Get model, RPM, and capacity information
            disk_info = self.parse_model(disk)
            metrics["Model"] = disk_info["Model"]
            metrics["RPM"] = disk_info["RPM"]
            metrics["Capacity"] = disk_info["Capacity"]
            
            # Collect detailed SMART attributes
            attr = self.parse_smart_attributes(disk)
            
            # Map collected attributes to configured metrics
            for metric, attr_id in self.config.metric_map.items():
                if metric not in ["Model", "RPM", "Capacity"]:  # Skip already collected metrics
                    value = attr.get(attr_id) or attr.get(metric, "N/A")
                    # Convert LBA values to GB
                    if metric in ["Total_LBAs_Written", "Total_LBAs_Read"]:
                        value = self.convert_lba_to_gb(value)
                    metrics[metric] = value

            # Check for alerts
            alerts = self.check_health_thresholds(disk, metrics)
            if alerts:
                self.alerts.extend(alerts)
                logger.warning(f"Alerts for {disk}: {alerts}")

            return metrics
        except Exception as e:
            logger.error(f"Error collecting metrics for {disk}: {str(e)}")
            return {metric: "ERROR" for metric in self.config.metric_map.keys()}

    def send_email_alert(self, report_path: str, alerts: List[str]) -> None:
        """
        Send email with SMART report and alerts
        Args:
            report_path: Path to the generated CSV report
            alerts: List of alert messages
        Raises:
            Exception: If email sending fails
        """
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['Subject'] = f"SMART Health Alert - {self.config.server_name}"
            msg['From'] = self.config.email_config.sender_email
            msg['To'] = ', '.join(self.config.email_recipients)

            # Add email body
            body = f"""
            SMART Health Alert for {self.config.server_name}
            
            The following alerts were detected:
            {chr(10).join(alerts)}
            
            Please find the detailed report attached.
            """
            msg.attach(MIMEText(body, 'plain'))

            # Attach the CSV report
            with open(report_path, 'rb') as f:
                report_attachment = MIMEApplication(f.read(), _subtype='csv')
                report_attachment.add_header(
                    'Content-Disposition', 
                    'attachment', 
                    filename=os.path.basename(report_path)
                )
                msg.attach(report_attachment)

            # Send email using SMTP
            with smtplib.SMTP(self.config.email_config.smtp_server, self.config.email_config.smtp_port) as server:
                if self.config.email_config.use_tls:
                    server.starttls()
                server.login(
                    self.config.email_config.sender_email,
                    self.config.email_config.app_password
                )
                server.send_message(msg)

            logger.info("Email alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            raise

    def handle_alerts(self, report_path: str):
        """
        Process any alerts that were detected
        Args:
            report_path: Path to the generated CSV report
        """
        if self.config.email_notification and self.alerts:
            logger.warning("Alerts detected that require notification")
            logger.warning("\n".join(self.alerts))
            self.send_email_alert(report_path, self.alerts)

    def generate_report(self) -> str:
        """
        Main method to generate the SMART report
        Returns:
            Path to the generated report file
        """
        logger.info("Starting report generation")
        
        # Collect metrics from all disks in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            disk_metrics = {
                disk: metrics for disk, metrics in zip(
                    self.config.disks,
                    executor.map(self.collect_disk_metrics, self.config.disks)
                )
            }

        # Generate report filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_path = self.config.output_dir / f"{self.config.server_name}_SMART_Report_{timestamp}.csv"

        # Write CSV report
        with open(report_path, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            # Write header row
            header = ["Metric", "Healthy Benchmark / Expectation"] + self.config.disks
            writer.writerow(header)

            # Write data rows
            for metric in self.config.healthy_benchmarks.keys():
                row = [metric, self.config.healthy_benchmarks.get(metric, "")]
                row.extend(disk_metrics[disk].get(metric, "N/A") for disk in self.config.disks)
                writer.writerow(row)

        logger.info(f"Report generated: {report_path}")
        
        # Process any alerts that were detected
        if self.alerts:
            self.handle_alerts(str(report_path))
            
        return str(report_path)

def main():
    """
    Main entry point of the script
    Handles command line arguments and orchestrates the report generation process
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate SMART health report")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    args = parser.parse_args()

    try:
        # Load configuration and generate report
        config = Config.from_file(args.config)
        generator = SmartReportGenerator(config)
        report_path = generator.generate_report()
        logger.info(f"Report generation completed successfully: {report_path}")
    except Exception as e:
        logger.error(f"Failed to generate report: {str(e)}")
        raise

# Script execution starts here
if __name__ == "__main__":
    main()
