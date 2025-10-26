from agents import RecordsWranglerAgent, SchedulingAgent, StatusAgent
from dotenv import load_dotenv
import os

load_dotenv()
os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')

import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Test Records Wrangler
print("Testing Records Wrangler...")
records_agent = RecordsWranglerAgent()
result = records_agent.process("Hey I need my medical records from Dr Smith for my car accident on May 15th. My name is John Doe born 3/20/1985")
print(f"Success: {result.get('success')}")
print(f"Quality: {records_agent.get_quality_score(result)}")
print()

# Test Scheduling
print("Testing Scheduling Agent...")
scheduling_agent = SchedulingAgent()
result = scheduling_agent.process("Hi this is Mike Chen, can we reschedule my consultation from Thursday to next week? Any day works for me.")
print(f"Success: {result.get('success')}")
print()

# Test Status
print("Testing Status Agent...")
status_agent = StatusAgent()
result = status_agent.process("Hey just checking in on my case status. Haven't heard anything in 2 weeks. This is Lisa Brown, case #12345")
print(f"Success: {result.get('success')}")