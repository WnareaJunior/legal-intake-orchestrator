from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime, timedelta
from agents import RecordsWranglerAgent, SchedulingAgent, StatusAgent

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
classifier_model = genai.GenerativeModel('gemini-2.0-flash-exp')

app = Flask(__name__)
CORS(app)

# Initialize specialist agents
AGENTS = {
    'records_request': RecordsWranglerAgent(),
    'scheduling': SchedulingAgent(),
    'status_update': StatusAgent()
}

# In-memory storage
messages = []
message_counter = 0


def create_demo_data():
    """Pre-populate with 5 demo messages"""
    global message_counter, messages
    
    demo_messages = [
        {
            "raw_text": "Hey I need my medical records from Dr Smith for my car accident on May 15th. My name is John Doe born 3/20/1985",
            "author": "John Doe",
            "header": "Medical Records Request for Car Accident Treatment",
            "task_type": "records_request",
            "confidence": 0.95,
            "reasoning": "Client requesting medical records related to a car accident",
            "minutes_ago": 2
        },
        {
            "raw_text": "hi its sarah johnson dob 6/12/1990 can u get my records from orlando health? i was there sept 20-23 for the slip and fall at walmart",
            "author": "Sarah Johnson",
            "header": "Records Request from Orlando Health Stay",
            "task_type": "records_request",
            "confidence": 0.92,
            "reasoning": "Client needs records from recent hospital stay",
            "minutes_ago": 5
        },
        {
            "raw_text": "Need records ASAP!!! John Martinez 4/5/78. Treatment at Florida Hospital after motorcycle crash last month. Dr. Patel was treating physician.",
            "author": "John Martinez",
            "header": "Urgent Medical Records - Motorcycle Accident",
            "task_type": "records_request",
            "confidence": 0.97,
            "reasoning": "Urgent request for motorcycle accident medical records",
            "minutes_ago": 8
        },
        {
            "raw_text": "Hi this is Mike Chen, can we reschedule my consultation from Thursday to next week? Any day works for me. Thanks!",
            "author": "Mike Chen",
            "header": "Reschedule Consultation to Next Week",
            "task_type": "scheduling",
            "confidence": 0.89,
            "reasoning": "Client wants to reschedule appointment",
            "minutes_ago": 12
        },
        {
            "raw_text": "Hey just checking in on my case status. Haven't heard anything in 2 weeks. This is Lisa Brown, case #12345",
            "author": "Lisa Brown",
            "header": "Case Status Update Request",
            "task_type": "status_update",
            "confidence": 0.91,
            "reasoning": "Client inquiring about case progress",
            "minutes_ago": 18
        }
    ]
    
    print("Generating demo data with agents...")
    # Generate drafts using agents
    for idx, demo in enumerate(demo_messages):
        message_counter += 1
        timestamp = datetime.now() - timedelta(minutes=demo['minutes_ago'])
        
        message_data = {
            "id": message_counter,
            "raw_text": demo["raw_text"],
            "author": demo["author"],
            "header": demo["header"],
            "task_type": demo["task_type"],
            "confidence": demo["confidence"],
            "reasoning": demo["reasoning"],
            "timestamp": timestamp.isoformat(),
            "draft": None,
            "status": "classified"
        }
        
        # Use agent to generate draft
        if demo["task_type"] in AGENTS:
            print(f"Processing demo message {idx + 1}/5 with {demo['task_type']} agent...")
            agent = AGENTS[demo["task_type"]]
            agent_result = agent.process(demo["raw_text"])
            
            if agent_result.get('success', False):
                message_data["draft"] = agent_result
                message_data["status"] = "draft_ready"
                message_data["agent_used"] = agent_result.get('agent')
                print(f"✓ Demo message {idx + 1} processed successfully")
            else:
                print(f"✗ Demo message {idx + 1} failed: {agent_result.get('error')}")
            
            # Small delay to avoid rate limits
            if idx < len(demo_messages) - 1:
                time.sleep(0.5)
        
        messages.append(message_data)
    
    print(f"Demo data ready: {len(messages)} messages loaded")

# Initialize demo data on startup
create_demo_data()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "AI Legal Tender",
        "agents_loaded": list(AGENTS.keys())
    })


@app.route('/classify', methods=['POST'])
def classify_message():
    """
    Orchestrator: Classifies message and routes to appropriate agent
    """
    global message_counter
    
    data = request.json
    raw_text = data.get('text', '')
    
    if not raw_text:
        return jsonify({"error": "No text provided"}), 400
    
    # Step 1: Classify using orchestrator
    classification_prompt = f"""You are a legal assistant classifier with strict quality standards. Analyze this client message and provide task details.

CRITICAL: Set confidence based on information completeness:
- records_request: Need patient name AND provider (else confidence < 0.5)
- scheduling: Need client name AND specific timing request (else confidence < 0.5)
- status_update: Need client name OR case number (else confidence < 0.5)

Analyze this message for:
1. Task category (see below)
2. Author name (extract from message, or use "Unknown Client")
3. A professional header/subject line (max 60 chars, summarize the request)
4. Quality assessment (missing key details lower confidence)

Categories:
- records_request: Client needs medical records, police reports, or other documents
- scheduling: Client wants to schedule/reschedule appointment or call
- status_update: Client asking about case status or progress
- other: Anything else

QUALITY RULES:
- Default to LOW confidence (0.4-0.5) for vague requests
- Records requests NEED patient name and provider (else confidence < 0.5)
- Schedule requests NEED timeframe (else confidence < 0.5)
- Status updates NEED case info (else confidence < 0.5)

Message:
{raw_text}

Respond ONLY with valid JSON in this exact format:
{{
    "task_type": "records_request",
    "confidence": 0.4,  // Default low unless specific details present
    "reasoning": "DETAILED quality assessment",
    "author": "Client Name or Unknown Client",
    "header": "Professional Subject Line",
    "quality_issues": ["List missing critical information"]
}}"""

    try:
        # Orchestrator makes classification decision
        response = classifier_model.generate_content(classification_prompt)
        result_text = response.text.strip()
        
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        classification = json.loads(result_text)
        
        # Quality pre-check based on task type
        quality_issues = classification.get('quality_issues', [])
        task_type = classification['task_type']
        confidence = classification['confidence']
        
        # Force lower confidence for quality issues
        if quality_issues:
            if task_type == 'records_request':
                if 'missing patient name' in quality_issues or 'missing provider' in quality_issues:
                    confidence = min(confidence, 0.4)  # Critical info missing
            elif task_type == 'scheduling':
                if 'missing timeframe' in quality_issues:
                    confidence = min(confidence, 0.45)  # Timing unclear
            elif task_type == 'status_update':
                if 'missing case info' in quality_issues:
                    confidence = min(confidence, 0.45)  # Can't identify case
        
        message_counter += 1
        message_data = {
            "id": message_counter,
            "raw_text": raw_text,
            "author": classification.get('author', 'Unknown Client'),
            "header": classification.get('header', 'New Message'),
            "task_type": task_type,
            "confidence": confidence,
            "reasoning": classification.get('reasoning', ''),
            "quality_issues": quality_issues,  # Include quality issues in response
            "timestamp": datetime.now().isoformat(),
            "draft": None,
            "status": "needs_details" if quality_issues else "classified"  # New status for low quality
        }
        messages.append(message_data)
        
        return jsonify(message_data)
        
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)}"}), 500


@app.route('/generate_draft/<int:message_id>', methods=['POST'])
def generate_draft(message_id):
    """
    Orchestrator routes message to appropriate specialist agent
    """
    message = next((m for m in messages if m['id'] == message_id), None)
    if not message:
        return jsonify({"error": "Message not found"}), 404
    
    task_type = message['task_type']
    
    # Check if we have an agent for this task type
    if task_type not in AGENTS:
        return jsonify({
            "error": f"No agent available for task type: {task_type}",
            "message": "Draft generation not yet supported for this message type"
        }), 400
    
    try:
        # Route to specialist agent
        agent = AGENTS[task_type]
        print(f"Routing to {agent.agent_name} for message {message_id}")
        
        # Agent processes autonomously
        agent_result = agent.process(message['raw_text'])
        
        if not agent_result.get('success', False):
            return jsonify({
                "error": "Agent processing failed",
                "details": agent_result.get('error', 'Unknown error')
            }), 500
        
        # Update message with agent's output
        message['draft'] = agent_result
        message['status'] = 'draft_ready'
        message['agent_used'] = agent_result.get('agent')
        message['agent_quality'] = agent.get_quality_score(agent_result)
        
        return jsonify(message)
        
    except Exception as e:
        return jsonify({"error": f"Draft generation failed: {str(e)}"}), 500


@app.route('/process_all', methods=['POST'])
def process_all():
    """
    Autonomous bulk processing - processes all classified messages
    This demonstrates autonomous agent behavior
    """
    pending = [m for m in messages if m['status'] == 'classified']
    
    if not pending:
        return jsonify({
            "message": "No pending messages to process",
            "processed": 0
        })
    
    results = []
    for idx, message in enumerate(pending):
        task_type = message['task_type']
        
        if task_type in AGENTS:
            try:
                print(f"Processing message {message['id']} with {task_type} agent...")
                agent = AGENTS[task_type]
                agent_result = agent.process(message['raw_text'])
                
                if agent_result.get('success', False):
                    message['draft'] = agent_result
                    message['status'] = 'draft_ready'
                    message['agent_used'] = agent_result.get('agent')
                    results.append({
                        "id": message['id'],
                        "success": True,
                        "agent": agent.agent_name
                    })
                    print(f"✓ Message {message['id']} processed successfully")
                else:
                    results.append({
                        "id": message['id'],
                        "success": False,
                        "error": agent_result.get('error')
                    })
                    print(f"✗ Message {message['id']} failed: {agent_result.get('error')}")
                
                # Small delay between messages to respect rate limits
                if idx < len(pending) - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                results.append({
                    "id": message['id'],
                    "success": False,
                    "error": str(e)
                })
                print(f"✗ Message {message['id']} exception: {str(e)}")
    
    return jsonify({
        "message": f"Processed {len(results)} messages",
        "processed": len(results),
        "results": results
    })


@app.route('/messages', methods=['GET'])
def get_messages():
    """Get all messages, sorted by newest first"""
    sorted_messages = sorted(messages, key=lambda x: x['timestamp'], reverse=True)
    return jsonify(sorted_messages)


@app.route('/message/<int:message_id>', methods=['GET'])
def get_message(message_id):
    """Get specific message"""
    message = next((m for m in messages if m['id'] == message_id), None)
    if not message:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(message)


@app.route('/decision/<int:message_id>', methods=['POST'])
def submit_decision(message_id):
    """Lawyer approves/edits/rejects draft"""
    message = next((m for m in messages if m['id'] == message_id), None)
    if not message:
        return jsonify({"error": "Message not found"}), 404
    
    data = request.json
    action = data.get('action')
    edited_draft = data.get('edited_draft')
    
    if action == 'approve':
        message['status'] = 'approved'
    elif action == 'edit':
        message['draft'] = edited_draft
        message['status'] = 'edited'
    elif action == 'reject':
        message['status'] = 'rejected'
    else:
        return jsonify({"error": "Invalid action"}), 400
    
    return jsonify(message)


@app.route('/agent_stats', methods=['GET'])
def agent_stats():
    """
    Show agent orchestration statistics
    Useful for demo - shows autonomous processing
    """
    stats = {
        "total_messages": len(messages),
        "by_status": {},
        "by_agent": {},
        "by_task_type": {}
    }
    
    for msg in messages:
        # Count by status
        status = msg['status']
        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        # Count by agent used
        if 'agent_used' in msg:
            agent = msg['agent_used']
            stats['by_agent'][agent] = stats['by_agent'].get(agent, 0) + 1
        
        # Count by task type
        task = msg['task_type']
        stats['by_task_type'][task] = stats['by_task_type'].get(task, 0) + 1
    
    return jsonify(stats)


if __name__ == '__main__':
    app.run(debug=True, port=5000)