# SMART Report Generator

A Python-based tool for generating comprehensive SMART (Self-Monitoring, Analysis, and Reporting Technology) health reports for hard drives. This tool monitors disk health, generates CSV reports, and sends email alerts for critical issues.

## Features

- **Comprehensive Disk Monitoring**
  - Overall SMART health status
  - Disk model and specifications (RPM, Capacity)
  - Detailed SMART attributes
  - Temperature monitoring
  - Error rate tracking
  - Usage statistics

- **Smart Reporting**
  - CSV format reports with timestamps
  - Parallel processing for multiple disks
  - Configurable metrics and thresholds
  - Healthy benchmark comparisons

- **Alert System**
  - Email notifications for critical issues
  - Configurable alert thresholds
  - Detailed alert messages
  - CSV report attachments

- **Robust Error Handling**
  - Retry mechanism for failed commands
  - Comprehensive logging
  - Graceful error recovery
  - Detailed error messages

## Prerequisites

- Python 3.6 or higher
- `smartmontools` package installed
- Sudo privileges (for running smartctl)
- Gmail account (for email notifications)

### Installing Prerequisites

```bash
# Install smartmontools
sudo yum install smartmontools  # For RHEL/CentOS
sudo apt-get install smartmontools  # For Ubuntu/Debian

# Install Python dependencies
pip install typing  # For Python 3.6 compatibility
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/smart-report-generator.git
cd smart-report-generator
```

2. Make the script executable:
```bash
chmod +x smart_report_1.py
```

3. Configure the script:
   - Copy `config.json.example` to `config.json`
   - Edit `config.json` with your settings

## Configuration

The `config.json` file contains all configuration settings:

```json
{
    "server_name": "your_server_name",
    "disks": ["/dev/sda", "/dev/sdb", "/dev/sdc"],
    "output_dir": "/var/log/smart_reports",
    "metric_map": {
        "RPM": "RPM",
        "Capacity": "Capacity",
        "Reallocated_Sector_Ct": "5",
        // ... other metrics
    },
    "healthy_benchmarks": {
        "Overall SMART Health": "PASSED",
        "Model": "As specified by vendor",
        // ... other benchmarks
    },
    "email_notification": true,
    "email_recipients": ["your.email@example.com"],
    "email_config": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "your.email@gmail.com",
        "app_password": "your_app_password",
        "use_tls": true
    },
    "alert_thresholds": {
        "Airflow_Temperature_Cel": 45.0,
        "Reallocated_Sector_Ct": 100.0,
        // ... other thresholds
    }
}
```

### Configuration Options

- **server_name**: Name of the server for report identification
- **disks**: List of disk devices to monitor
- **output_dir**: Directory for storing reports
- **metric_map**: Mapping of SMART attributes to readable names
- **healthy_benchmarks**: Expected values for various metrics
- **email_notification**: Enable/disable email alerts
- **email_recipients**: List of email addresses for alerts
- **email_config**: SMTP server settings
- **alert_thresholds**: Critical values that trigger alerts

### Setting up Gmail for Notifications

1. Enable 2-Step Verification in your Google Account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a new app password for "Mail"
   - Use this password in the config file

## Usage

### Basic Usage

```bash
sudo ./smart_report_1.py --config config.json
```

### Command Line Arguments

- `--config`: Path to configuration file (default: config.json)

### Output

The script generates:
1. CSV report in the specified output directory
2. Log file at `/var/log/smart_report.log`
3. Email alerts for critical issues

### Report Format

The CSV report includes:
- Overall SMART health status
- Disk model and specifications
- RPM and capacity
- SMART attributes with values
- Comparison against healthy benchmarks

## SMART Attributes Explained

The script monitors several important SMART attributes:

1. **Reallocated_Sector_Ct (ID: 5)**
   - Count of reallocated sectors
   - Higher values indicate disk wear

2. **Raw_Read_Error_Rate (ID: 1)**
   - Rate of read errors
   - Vendor-specific interpretation

3. **Start_Stop_Count (ID: 4)**
   - Number of disk start/stop cycles
   - Higher values indicate more wear

4. **Power_On_Hours (ID: 9)**
   - Total power-on time
   - Usage dependent metric

5. **Temperature (ID: 190)**
   - Current disk temperature
   - Critical for drive longevity

6. **Total_LBAs_Written/Read (ID: 241/242)**
   - Total data written/read
   - Converted to GB for readability

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Shivang Gupta - [shivanggupta2611@gmail.com](mailto:shivanggupta2611@gmail.com)

## Acknowledgments

- smartmontools team for the excellent SMART monitoring tools
- Python community for the rich ecosystem of libraries 
