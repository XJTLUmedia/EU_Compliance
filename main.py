#!/usr/bin/env python3
"""
Main entry point for the EU Regulatory Compliance Consulting Service
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
import signal
import threading
import time

# Import our custom classes
from eu_regulatory_scraper import EURegulatoryScraper
from ai_compliance_analyzer import AIComplianceAnalyzer
from report_generator import ComplianceReportGenerator
from monitoring_system import ComplianceMonitoringSystem
from web_app import app as web_app, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ComplianceService:
    """
    Main service class for the EU Regulatory Compliance Consulting Service
    """
    
    def __init__(self, config_file='config.json'):
        """
        Initialize the service with configuration
        """
        self.config = self._load_config(config_file)
        self.running = False
        self.threads = []
        
        # Initialize components
        self.scraper = EURegulatoryScraper()
        self.analyzer = AIComplianceAnalyzer(api_key=self.config.get('deepseek_api_key'))
        self.report_generator = ComplianceReportGenerator()
        self.monitoring_system = ComplianceMonitoringSystem(config_file)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Compliance Service initialized")
    
    def _load_config(self, config_file):
        """
        Load configuration from file
        """
        default_config = {
            'deepseek_api_key': os.environ.get('DEEPSEEK_API_KEY', 'your-deepseek-api-key'),
            'email': {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': os.environ.get('EMAIL_USERNAME', 'your-email@gmail.com'),
                'password': os.environ.get('EMAIL_PASSWORD', 'your-app-password')
            },
            'monitoring': {
                'check_interval_hours': 24,
                'alert_threshold': 3
            },
            'web_app': {
                'secret_key': os.environ.get('SECRET_KEY', 'your-very-secure-secret-key-here'),
                'host': '0.0.0.0',
                'port': 5001,
                'debug': False
            },
            'reports': {
                'output_dir': 'reports',
                'logo_path': 'static/logo.png'
            },
            'database': {
                'type': 'sqlite',
                'path': 'compliance.db'
            },
            'deepseek': {
                'api_base': 'https://api.deepseek.com/v1',
                'model': 'deepseek_reasoner',
                'max_tokens': 2000,
                'temperature': 0.3,
                'max_retries': 3,
                'retry_delay': 1
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with default config to ensure all keys exist
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                        elif isinstance(value, dict) and isinstance(config.get(key), dict):
                            # Recursively merge nested dictionaries
                            for subkey, subvalue in value.items():
                                if subkey not in config[key]:
                                    config[key][subkey] = subvalue
                    return config
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
                return default_config
        else:
            # Create default config file
            try:
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info(f"Created default config file: {config_file}")
            except Exception as e:
                logger.error(f"Error creating config file: {str(e)}")
            return default_config
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals
        """
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
    
    def run_scraper(self):
        """
        Run the regulatory scraper to get the latest updates
        """
        logger.info("Running EU Regulatory Scraper...")
        try:
            updates = self.scraper.check_for_updates()
            
            logger.info(f"Scraped updates for {len(updates)} regulation types:")
            for regulation_type, regulation_updates in updates.items():
                logger.info(f"  {regulation_type}: {len(regulation_updates)} updates")
            
            return updates
        except Exception as e:
            logger.error(f"Error running scraper: {str(e)}")
            return {}
    
    def run_analysis(self, business_info_file):
        """
        Run compliance analysis for a business
        """
        logger.info("Running Compliance Analysis...")
        
        # Load business information
        try:
            with open(business_info_file, 'r') as f:
                business_info = json.load(f)
        except Exception as e:
            logger.error(f"Error loading business information: {str(e)}")
            return None
        
        try:
            # Run analysis
            analysis_result = self.analyzer.analyze_compliance(business_info)
            
            # Generate roadmap
            roadmap = self.analyzer.generate_compliance_roadmap(analysis_result)
            
            # Estimate costs
            cost_estimate = self.analyzer.estimate_compliance_costs(analysis_result)
            
            # Generate reports
            compliance_report_path = self.report_generator.generate_compliance_report(analysis_result, business_info)
            roadmap_report_path = self.report_generator.generate_roadmap_report(roadmap, business_info)
            
            logger.info(f"Analysis complete. Compliance score: {analysis_result.get('overall_compliance_score', 'N/A')}/100")
            logger.info(f"Compliance report saved to: {compliance_report_path}")
            logger.info(f"Roadmap report saved to: {roadmap_report_path}")
            
            return {
                'analysis_result': analysis_result,
                'roadmap': roadmap,
                'cost_estimate': cost_estimate,
                'compliance_report_path': compliance_report_path,
                'roadmap_report_path': roadmap_report_path
            }
            
        except Exception as e:
            logger.error(f"Error running analysis: {str(e)}")
            return None
    
    def run_monitoring(self):
        """
        Run the monitoring system
        """
        logger.info("Starting Compliance Monitoring System...")
        try:
            self.monitoring_system.start_monitoring()
        except KeyboardInterrupt:
            logger.info("Monitoring system stopped by user")
        except Exception as e:
            logger.error(f"Error in monitoring system: {str(e)}")
    
    def run_web_server(self):
        """
        Run the web application server
        """
        logger.info("Starting Web Application Server...")
        
        # Initialize database
        try:
            init_db()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            return
        
        # Configure Flask app
        web_app.secret_key = self.config.get('web_app', {}).get('secret_key', 'your-secret-key-here')
        web_app.config['DEBUG'] = self.config.get('web_app', {}).get('debug', False)
        
        # Get host and port from config
        host = self.config.get('web_app', {}).get('host', '0.0.0.0')
        port = self.config.get('web_app', {}).get('port', 5001)
        
        try:
            web_app.run(host=host, port=port, debug=False)
        except Exception as e:
            logger.error(f"Error running web server: {str(e)}")
    
    def run_all_services(self):
        """
        Run all services in separate threads
        """
        logger.info("Starting all services...")
        
        # Start monitoring system in a separate thread
        monitoring_thread = threading.Thread(target=self.run_monitoring, daemon=True)
        monitoring_thread.start()
        self.threads.append(monitoring_thread)
        
        # Start web server in the main thread
        self.run_web_server()
    
    def shutdown(self):
        """
        Shutdown the service gracefully
        """
        logger.info("Shutting down Compliance Service...")
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("Compliance Service shutdown complete")
        sys.exit(0)

def main():
    """
    Main function to handle command line arguments
    """
    parser = argparse.ArgumentParser(description='EU Regulatory Compliance Consulting Service')
    parser.add_argument('command', choices=['scraper', 'analysis', 'monitoring', 'web', 'all'],
                        help='Command to run')
    parser.add_argument('--business-info', type=str, help='Path to business information JSON file (for analysis)')
    parser.add_argument('--config', type=str, default='config.json', help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Create service instance
    service = ComplianceService(args.config)
    
    if args.command == 'scraper':
        service.run_scraper()
    elif args.command == 'analysis':
        if not args.business_info:
            logger.error("--business-info is required for analysis command")
            sys.exit(1)
        service.run_analysis(args.business_info)
    elif args.command == 'monitoring':
        service.run_monitoring()
    elif args.command == 'web':
        service.run_web_server()
    elif args.command == 'all':
        service.run_all_services()

if __name__ == '__main__':
    main()