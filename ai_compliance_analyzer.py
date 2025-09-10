import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Any
import time

class AIComplianceAnalyzer:
    """
    Uses DeepSeek AI to analyze EU regulations and generate compliance recommendations
    """
    
    def __init__(self, api_key):
        """
        Initialize the analyzer with DeepSeek API key
        """
        self.api_key = api_key
        self.api_base = "https://api.deepseek.com/v1"
        self.model = "deepseek_reasoner"  # Using DeepSeek's chat model
        
        # System prompt for regulatory analysis
        self.system_prompt = """
        You are an expert EU regulatory compliance consultant specializing in GDPR, 
        Digital Services Act, and AI Act. Your task is to analyze business activities 
        against EU regulations and provide detailed compliance recommendations.
        
        For each analysis, provide:
        1. Relevant regulatory requirements
        2. Current compliance gaps
        3. Specific action items to achieve compliance
        4. Timeline and priority for each action
        5. Potential risks of non-compliance
        
        Format your response as a structured JSON object with the following keys:
        - regulatory_requirements: array of strings
        - compliance_gaps: array of strings
        - action_items: array of objects with keys: action, priority, timeline, estimated_cost
        - risks: array of strings
        - overall_compliance_score: integer from 0-100
        """
    
    def analyze_compliance(self, business_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze business activities against EU regulations
        """
        # Construct the user prompt based on business information
        user_prompt = self._construct_prompt(business_info)
        
        try:
            # Call the DeepSeek API
            response = self._call_deepseek_api([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
            # Extract the response content
            response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Parse the JSON response
            try:
                analysis_result = json.loads(response_content)
            except json.JSONDecodeError:
                # If the response is not valid JSON, create a structured result
                analysis_result = {
                    "regulatory_requirements": ["Error parsing AI response"],
                    "compliance_gaps": ["Please try again"],
                    "action_items": [],
                    "risks": ["Unable to complete analysis"],
                    "overall_compliance_score": 0,
                    "raw_response": response_content
                }
            
            # Add metadata
            analysis_result['analysis_date'] = datetime.now().isoformat()
            analysis_result['business_info'] = business_info
            
            return analysis_result
            
        except Exception as e:
            return {
                "error": str(e),
                "regulatory_requirements": [],
                "compliance_gaps": [],
                "action_items": [],
                "risks": ["Unable to complete analysis due to technical error"],
                "overall_compliance_score": 0,
                "analysis_date": datetime.now().isoformat()
            }
    
    def _call_deepseek_api(self, messages):
        """
        Make a call to the DeepSeek API
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for more consistent results
            "max_tokens": 2000
        }
        
        # Implement retry logic for API calls
        max_retries = 3
        retry_delay = 1  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30  # 30 second timeout
                )
                
                # Check if the request was successful
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"API request failed with status {response.status_code}: {response.text}"
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt + 1} failed: {error_message}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise Exception(error_message)
                        
            except (requests.RequestException, json.JSONDecodeError) as e:
                error_message = f"API request error: {str(e)}"
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed: {error_message}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise Exception(error_message)
        
        raise Exception("Max retries exceeded")
    
    def _construct_prompt(self, business_info: Dict[str, Any]) -> str:
        """
        Construct a detailed prompt for the AI based on business information
        """
        prompt = f"""
        Please analyze the following business for EU regulatory compliance:
        
        Business Name: {business_info.get('business_name', 'Unknown')}
        Industry: {business_info.get('industry', 'Unknown')}
        Business Activities: {business_info.get('business_activities', 'Unknown')}
        Target Markets: {business_info.get('target_markets', 'Unknown')}
        Data Processing Activities: {business_info.get('data_processing', 'Unknown')}
        AI Systems in Use: {business_info.get('ai_systems', 'None')}
        Online Services Provided: {business_info.get('online_services', 'Unknown')}
        Current Compliance Measures: {business_info.get('current_compliance', 'None')}
        
        Please provide a comprehensive compliance analysis covering GDPR, Digital Services Act, and AI Act.
        """
        
        return prompt
    
    def generate_compliance_roadmap(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a compliance roadmap based on the analysis results
        """
        roadmap_prompt = f"""
        Based on the following compliance analysis, create a detailed 12-month compliance roadmap:
        
        {json.dumps(analysis_result, indent=2)}
        
        The roadmap should include:
        1. Monthly milestones
        2. Resource requirements (staff, budget, tools)
        3. Key performance indicators to track progress
        4. Critical path items that could delay the entire process
        5. Contingency plans for common challenges
        
        Format your response as a structured JSON object.
        """
        
        try:
            response = self._call_deepseek_api([
                {"role": "system", "content": "You are an expert compliance project manager."},
                {"role": "user", "content": roadmap_prompt}
            ])
            
            response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            try:
                roadmap = json.loads(response_content)
            except json.JSONDecodeError:
                roadmap = {
                    "error": "Could not parse roadmap",
                    "raw_response": response_content
                }
            
            return roadmap
            
        except Exception as e:
            return {
                "error": str(e),
                "message": "Could not generate roadmap"
            }
    
    def estimate_compliance_costs(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate costs for implementing compliance measures
        """
        cost_prompt = f"""
        Based on the following compliance analysis, provide a detailed cost estimate for implementing all recommended actions:
        
        {json.dumps(analysis_result, indent=2)}
        
        The cost estimate should include:
        1. One-time costs (consulting, software, training)
        2. Annual recurring costs (staff, maintenance, subscriptions)
        3. Potential fines for non-compliance (worst-case scenario)
        4. ROI calculation for compliance investments
        5. Cost-saving opportunities through efficient compliance
        
        Format your response as a structured JSON object.
        """
        
        try:
            response = self._call_deepseek_api([
                {"role": "system", "content": "You are an expert compliance cost estimator."},
                {"role": "user", "content": cost_prompt}
            ])
            
            response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            try:
                cost_estimate = json.loads(response_content)
            except json.JSONDecodeError:
                cost_estimate = {
                    "error": "Could not parse cost estimate",
                    "raw_response": response_content
                }
            
            return cost_estimate
            
        except Exception as e:
            return {
                "error": str(e),
                "message": "Could not estimate costs"
            }