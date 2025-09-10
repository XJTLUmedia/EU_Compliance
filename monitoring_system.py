import schedule
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime, timedelta
import logging
import requests

# Import our custom classes
from eu_regulatory_scraper import EURegulatoryScraper
from ai_compliance_analyzer import AIComplianceAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('compliance_monitoring.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ComplianceMonitoringSystem:
    """
    Monitors regulatory changes and alerts clients
    """
    
    def __init__(self, config_file='config.json'):
        """
        Initialize the monitoring system
        """
        # Ensure logger exists before calling any methods that log
        self.logger = logging.getLogger(__name__)

        self.config = self._load_config(config_file)
        self.scraper = EURegulatoryScraper()
        self.analyzer = AIComplianceAnalyzer(api_key=self.config.get('deepseek_api_key'))

        # Database for storing regulatory updates and client alerts
        self.regulatory_updates_db = 'regulatory_updates.json'
        self.client_alerts_db = 'client_alerts_db.json'
        self.clients_db = 'clients_db.json'

        # Initialize databases if they don't exist
        self._init_databases()
    
    def _load_config(self, config_file):
        """
        Load configuration from file
        """
        default_config = {
            'deepseek_api_key': 'your-deepseek-api-key',
            'email': {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'your-email@gmail.com',
                'password': 'your-app-password'
            },
            'monitoring': {
                'check_interval_hours': 24,
                'alert_threshold': 3
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
                    return config
            except Exception as e:
                self.logger.error(f"Error loading config file: {str(e)}")
                return default_config
        else:
            # Create default config file
            try:
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                self.logger.info(f"Created default config file: {config_file}")
            except Exception as e:
                self.logger.error(f"Error creating config file: {str(e)}")
            return default_config
    
    def _init_databases(self):
        """
        Initialize databases if they don't exist
        """
        for db_file in [self.regulatory_updates_db, self.client_alerts_db, self.clients_db]:
            if not os.path.exists(db_file):
                with open(db_file, 'w') as f:
                    json.dump({}, f)
                self.logger.info(f"Initialized database: {db_file}")
    
    def check_regulatory_updates(self):
        """
        Check for regulatory updates and store them
        """
        self.logger.info("Checking for regulatory updates...")
        
        # Load existing updates
        try:
            with open(self.regulatory_updates_db, 'r') as f:
                existing_updates = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading regulatory updates: {str(e)}")
            existing_updates = {}
        
        # Get new updates
        try:
            new_updates = self.scraper.check_for_updates()
        except Exception as e:
            self.logger.error(f"Error checking for updates: {str(e)}")
            return False
        
        # Check for new items
        has_new_updates = False
        for regulation_type, updates in new_updates.items():
            if regulation_type not in existing_updates:
                existing_updates[regulation_type] = []
            
            # Check each update to see if it's new
            for update in updates:
                # Simple check based on title (in production, use more sophisticated deduplication)
                is_new = True
                for existing_update in existing_updates[regulation_type]:
                    if existing_update.get('title') == update.get('title'):
                        is_new = False
                        break
                
                if is_new:
                    update['discovered_date'] = datetime.now().isoformat()
                    existing_updates[regulation_type].append(update)
                    has_new_updates = True
                    self.logger.info(f"New update found for {regulation_type}: {update.get('title')}")
        
        # Save updates
        if has_new_updates:
            try:
                with open(self.regulatory_updates_db, 'w') as f:
                    json.dump(existing_updates, f, indent=2)
                self.logger.info("Saved updated regulatory data")
                
                # Check if we need to send alerts
                self._check_and_send_alerts()
            except Exception as e:
                self.logger.error(f"Error saving regulatory updates: {str(e)}")
        
        return has_new_updates
    
    def _check_and_send_alerts(self):
        """
        Check if alert threshold is reached and send alerts to clients
        """
        # Load updates and alerts
        try:
            with open(self.regulatory_updates_db, 'r') as f:
                updates = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading regulatory updates: {str(e)}")
            return
        
        try:
            with open(self.client_alerts_db, 'r') as f:
                client_alerts = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading client alerts: {str(e)}")
            client_alerts = {}
        
        try:
            with open(self.clients_db, 'r') as f:
                clients = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading clients: {str(e)}")
            clients = {}
        
        # Count recent updates (last 7 days)
        threshold_date = (datetime.now() - timedelta(days=7)).isoformat()
        recent_update_count = 0
        
        for regulation_type, regulation_updates in updates.items():
            for update in regulation_updates:
                if update.get('discovered_date', '') >= threshold_date:
                    recent_update_count += 1
        
        # Check if threshold is reached
        alert_threshold = self.config.get('monitoring', {}).get('alert_threshold', 3)
        
        if recent_update_count >= alert_threshold:
            self.logger.info(f"Alert threshold reached: {recent_update_count} updates in the last 7 days")
            
            # Send alerts to all clients
            self._send_alerts_to_clients(updates, clients, client_alerts)
            
            # Update alert history
            alert_id = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            client_alerts[alert_id] = {
                'id': alert_id,
                'date': datetime.now().isoformat(),
                'update_count': recent_update_count,
                'updates_sent': True
            }
            
            # Save alert history
            try:
                with open(self.client_alerts_db, 'w') as f:
                    json.dump(client_alerts, f, indent=2)
                self.logger.info("Updated alert history")
            except Exception as e:
                self.logger.error(f"Error saving alert history: {str(e)}")
    
    def _send_alerts_to_clients(self, updates, clients, client_alerts):
        """
        Send email alerts to all clients about regulatory updates
        """
        # Prepare email content
        subject = "EU Regulatory Compliance Alert - Important Updates"
        
        # Create HTML email body
        html_body = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                .header { background-color: #f8f9fa; padding: 20px; text-align: center; }
                .content { padding: 20px; }
                .regulation { margin-bottom: 20px; padding: 15px; border-left: 4px solid #007bff; background-color: #f8f9fa; }
                .update { margin-bottom: 10px; }
                .footer { padding: 20px; text-align: center; font-size: 12px; color: #6c757d; }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>EU Regulatory Compliance Alert</h2>
                <p>Important updates to EU regulations that may affect your compliance obligations</p>
            </div>
            <div class="content">
        """
        
        # Add regulation updates
        for regulation_type, regulation_updates in updates.items():
            html_body += f'<div class="regulation"><h3>{regulation_type.upper()}</h3>'
            
            # Show only the 3 most recent updates
            recent_updates = sorted(regulation_updates, key=lambda x: x.get('discovered_date', ''), reverse=True)[:3]
            
            for update in recent_updates:
                html_body += f'''
                <div class="update">
                    <h4>{update.get('title', 'Untitled')}</h4>
                    <p><strong>Date:</strong> {update.get('date', 'Unknown')}</p>
                    <p>{update.get('content', 'No content available')}</p>
                    <p><a href="{update.get('url', '#')}">Read more</a></p>
                </div>
                '''
            
            html_body += '</div>'
        
        html_body += """
                <p>These updates may impact your compliance obligations. We recommend reviewing them with your legal team.</p>
                <p>If you need assistance assessing the impact of these changes on your business, please reply to this email to schedule a consultation.</p>
            </div>
            <div class="footer">
                <p>This is an automated alert from the EU Regulatory Compliance Monitoring Service.</p>
                <p>To unsubscribe from these alerts, please reply with "UNSUBSCRIBE" in the subject line.</p>
            </div>
        </body>
        </html>
        """
        
        # Send emails to all clients
        email_config = self.config.get('email', {})
        
        for client_id, client_info in clients.items():
            try:
                # Create message
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = email_config.get('username')
                msg['To'] = client_info.get('email', '')
                
                # Attach HTML body
                msg.attach(MIMEText(html_body, 'html'))
                
                # Send email
                server = smtplib.SMTP(email_config.get('smtp_server'), email_config.get('smtp_port'))
                server.starttls()
                server.login(email_config.get('username'), email_config.get('password'))
                
                text = msg.as_string()
                server.sendmail(email_config.get('username'), client_info.get('email', ''), text)
                server.quit()
                
                self.logger.info(f"Alert sent to {client_info.get('email', '')}")
                
            except Exception as e:
                self.logger.error(f"Failed to send alert to {client_info.get('email', '')}: {str(e)}")
    
    def assess_impact_of_updates(self, client_business_info):
        """
        Assess the impact of recent regulatory updates on a specific client
        """
        # Load recent updates
        try:
            with open(self.regulatory_updates_db, 'r') as f:
                updates = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading regulatory updates: {str(e)}")
            return {"error": "Could not load regulatory updates"}
        
        # Get updates from the last 30 days
        threshold_date = (datetime.now() - timedelta(days=30)).isoformat()
        recent_updates = {}
        
        for regulation_type, regulation_updates in updates.items():
            recent_updates[regulation_type] = []
            for update in regulation_updates:
                if update.get('discovered_date', '') >= threshold_date:
                    recent_updates[regulation_type].append(update)
        
        # Use AI to assess impact
        impact_prompt = f"""
        Based on the following recent EU regulatory updates, assess the potential impact on a business with the following profile:
        
        Business Profile:
        {json.dumps(client_business_info, indent=2)}
        
        Recent Regulatory Updates:
        {json.dumps(recent_updates, indent=2)}
        
        Please provide:
        1. Overall impact assessment (Low, Medium, High)
        2. Specific areas of concern
        3. Recommended actions
        4. Timeline for response
        
        Format your response as a structured JSON object.
        """
        
        try:
            response = self.analyzer._call_deepseek_api([
                {"role": "system", "content": "You are an expert EU regulatory compliance consultant."},
                {"role": "user", "content": impact_prompt}
            ])
            
            response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            try:
                impact_assessment = json.loads(response_content)
            except json.JSONDecodeError:
                impact_assessment = {
                    "error": "Could not parse impact assessment",
                    "raw_response": response_content
                }
            
            return impact_assessment
            
        except Exception as e:
            self.logger.error(f"Error assessing impact of updates: {str(e)}")
            return {
                "error": str(e),
                "message": "Could not assess impact of updates"
            }
    
    def start_monitoring(self):
        """
        Start the monitoring system with scheduled checks
        """
        # Schedule regulatory update checks
        check_interval = self.config.get('monitoring', {}).get('check_interval_hours', 24)
        schedule.every(check_interval).hours.do(self.check_regulatory_updates)
        
        self.logger.info(f"Monitoring system started. Checking for updates every {check_interval} hours.")
        
        # Run the scheduler
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Monitoring system stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(60)  # Wait before retrying

# Example usage
if __name__ == "__main__":
    monitoring_system = ComplianceMonitoringSystem()
    
    # Run a one-time check
    monitoring_system.check_regulatory_updates()
    
    # Start continuous monitoring (uncomment to run continuously)
    # monitoring_system.start_monitoring()