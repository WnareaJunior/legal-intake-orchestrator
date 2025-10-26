from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime, timedelta
from agents import RecordsWranglerAgent, SchedulingAgent, StatusAgent
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
classifier_model = genai.GenerativeModel('gemini-2.5-flash')

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

def process_multi_provider_message(message):
    """
    Process a message that may have multiple providers
    Returns the message with provider-specific drafts
    """
    task_type = message['task_type']
    
    if task_type != 'records_request':
        return message  # Not a records request
    
    agent = AGENTS.get(task_type)
    if not agent:
        return message
    
    try:
        agent_result = agent.process(message['raw_text'])
        
        if not agent_result.get('success', False):
            message['draft'] = agent_result
            message['status'] = 'draft_ready'
            return message
        
        # Check if multiple providers detected
        provider_count = agent_result.get('provider_count', 1)
        
        if provider_count > 1 and agent_result.get('requires_multiple_requests', False):
            # Generate individual drafts for each provider
            individual_drafts = agent.generate_individual_drafts(agent_result)
            
            message['draft'] = agent_result  # Master draft
            message['provider_drafts'] = individual_drafts  # Individual drafts
            message['status'] = 'multi_provider_ready'
            message['agent_used'] = agent_result.get('agent')
            message['provider_count'] = provider_count
        else:
            # Single provider
            message['draft'] = agent_result
            message['status'] = 'draft_ready'
            message['agent_used'] = agent_result.get('agent')
            message['provider_count'] = 1
        
        return message
        
    except Exception as e:
        print(f"Error processing multi-provider: {e}")
        return message

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
            #if idx < len(demo_messages) - 1:
                #time.sleep(0.5)
        
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

@app.route('/generate_complex_message', methods=['GET'])
def generate_complex_message():
    """Generate a complex multi-provider test message"""
    return jsonify({
        "message": "Hi, I need medical records for my car accident case. I'm Sarah Martinez, DOB 6/15/1988. After the accident on May 15th, I was taken to Orlando Health ER, then transferred to Florida Hospital for surgery on May 16th. I had follow-up appointments with Dr. Patel at the orthopedic clinic in June, and also saw Dr. Anderson for physical therapy at AdventHealth from June through August. I need all records from all these providers ASAP for my case. Thanks!"
    })

@app.route('/generate_draft/<int:message_id>', methods=['POST'])
def generate_draft(message_id):
    """
    Orchestrator routes message to appropriate specialist agent
    """
    message = next((m for m in messages if m['id'] == message_id), None)
    if not message:
        return jsonify({"error": "Message not found"}), 404
    
    task_type = message['task_type']
    
    if task_type not in AGENTS:
        return jsonify({
            "error": f"No agent available for task type: {task_type}",
            "message": "Draft generation not yet supported for this message type"
        }), 400
    
    try:
        agent = AGENTS[task_type]
        print(f"Routing to {agent.agent_name} for message {message_id}")
        
        agent_result = agent.process(message['raw_text'])
        
        if not agent_result.get('success', False):
            return jsonify({
                "error": "Agent processing failed",
                "details": agent_result.get('error', 'Unknown error')
            }), 500
        
        # Check for multi-provider
        provider_count = agent_result.get('provider_count', 1)
        
        if provider_count > 1 and task_type == 'records_request':
            # Multi-provider detected!
            message['draft'] = agent_result
            message['provider_count'] = provider_count
            message['status'] = 'multi_provider_ready'
            message['agent_used'] = agent_result.get('agent')
            
            # Generate individual drafts
            if hasattr(agent, 'generate_individual_drafts'):
                message['provider_drafts'] = agent.generate_individual_drafts(agent_result)
        else:
            # Single provider
            message['draft'] = agent_result
            message['status'] = 'draft_ready'
            message['agent_used'] = agent_result.get('agent')
        
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

@app.route('/process_bulk', methods=['POST'])
def process_bulk():
    """
    Process multiple messages in TRUE PARALLEL - SPEED DEMON MODE
    Uses batch classification and parallel agent processing
    """
    data = request.json
    message_texts = data.get('messages', [])
    
    if not message_texts or len(message_texts) == 0:
        return jsonify({"error": "No messages provided"}), 400
    
    if len(message_texts) > 100:
        return jsonify({"error": "Maximum 100 messages at once"}), 400
    
    print(f"🚀 BULK PROCESSING: {len(message_texts)} messages")
    start_time = datetime.now()
    
    global message_counter
    
    # Step 1: Quick classification (simplified for speed)
    classified_messages = []
    
    for idx, text in enumerate(message_texts):
        message_counter += 1
        
        # Fast heuristic classification (no Gemini call for speed)
        task_type = "other"
        confidence = 0.75
        author = "Unknown Client"
        
        text_lower = text.lower()
        
        # Simple keyword matching for speed
        if any(word in text_lower for word in ["record", "medical", "hospital", "doctor", "dr.", "treatment"]):
            task_type = "records_request"
            confidence = 0.85
        elif any(word in text_lower for word in ["schedule", "reschedule", "appointment", "meeting", "consultation"]):
            task_type = "scheduling"
            confidence = 0.80
        elif any(word in text_lower for word in ["status", "update", "case", "progress", "checking"]):
            task_type = "status_update"
            confidence = 0.80
        
        # Try to extract name (simple heuristic)
        words = text.split()
        if len(words) >= 2:
            # Look for "I'm NAME" or "This is NAME" or "NAME here"
            for i, word in enumerate(words):
                if word.lower() in ["im", "i'm", "this", "is"] and i + 1 < len(words):
                    potential_name = words[i + 1:min(i + 3, len(words))]
                    author = " ".join(potential_name).strip(",.!?")
                    break
        
        message_data = {
            "id": message_counter,
            "raw_text": text,
            "author": author,
            "header": f"{task_type.replace('_', ' ').title()} - {author}",
            "task_type": task_type,
            "confidence": confidence,
            "reasoning": f"Fast bulk classification (message {idx + 1}/{len(message_texts)})",
            "timestamp": datetime.now().isoformat(),
            "draft": None,
            "status": "classified",
            "bulk_batch": True
        }
        
        classified_messages.append(message_data)
        messages.append(message_data)
    
    print(f"✓ Classified {len(classified_messages)} messages in {(datetime.now() - start_time).total_seconds():.2f}s")
    
    # Step 2: Process drafts in BATCHES (5 at a time to avoid rate limits)
    batch_size = 5
    results = []
    
    for batch_start in range(0, len(classified_messages), batch_size):
        batch = classified_messages[batch_start:batch_start + batch_size]
        batch_results = []
        
        print(f"Processing batch {batch_start // batch_size + 1} ({len(batch)} messages)...")
        
        # Process batch with thread pool
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            def process_single(msg):
                task_type = msg['task_type']
                
                if task_type not in AGENTS:
                    return {
                        "id": msg['id'],
                        "success": False,
                        "error": "No agent for this task type"
                    }
                
                try:
                    agent = AGENTS[task_type]
                    # Reduce retries for speed
                    original_retries = agent.max_retries
                    agent.max_retries = 1  # Only 1 attempt in bulk mode
                    
                    agent_result = agent.process(msg['raw_text'])
                    
                    agent.max_retries = original_retries  # Restore
                    
                    if agent_result.get('success', False):
                        msg['draft'] = agent_result
                        msg['status'] = 'draft_ready'
                        msg['agent_used'] = agent_result.get('agent')
                        
                        return {
                            "id": msg['id'],
                            "success": True,
                            "agent": agent.agent_name,
                            "quality": agent_result.get('quality_score', 0)
                        }
                    else:
                        return {
                            "id": msg['id'],
                            "success": False,
                            "error": agent_result.get('error', 'Unknown error')
                        }
                        
                except Exception as e:
                    return {
                        "id": msg['id'],
                        "success": False,
                        "error": str(e)
                    }
            
            batch_results = list(executor.map(process_single, batch))
        
        results.extend(batch_results)
        
        # Small delay between batches (not between individual messages)
        if batch_start + batch_size < len(classified_messages):
            time.sleep(0.5)
    
    # Calculate metrics
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    successful = sum(1 for r in results if r.get('success', False))
    failed = len(results) - successful
    
    print(f"✓ BULK COMPLETE: {successful}/{len(results)} successful in {duration:.2f}s")
    
    return jsonify({
        "message": f"Bulk processing complete",
        "total": len(message_texts),
        "classified": len(classified_messages),
        "processed": len(results),
        "successful": successful,
        "failed": failed,
        "duration_seconds": round(duration, 2),
        "messages_per_second": round(len(results) / duration, 2) if duration > 0 else 0,
        "results": results,
        "new_messages": [m['id'] for m in classified_messages]
    })

@app.route('/generate_test_messages', methods=['GET'])
def generate_test_messages():
    """
    Generate realistic test messages for bulk processing demo
    Returns 20 sample messages
    """
    templates = [
        "Hi I need my medical records from {provider}. My name is {name}, DOB {dob}. I was treated for {condition} on {date}.",
        "Hey its {name}, can I get records from {provider}? Birth date {dob}, saw them for {condition} last month.",
        "Need records ASAP from Dr. {provider}! {name} born {dob}, treatment for {condition}.",
        "Hello, this is {name}. Can we schedule a consultation next week? Any day works for me.",
        "Hi {name} here, need to reschedule my appointment from Thursday to sometime next week.",
        "Can we move my {appt_type} to {day}? This is {name}, thanks!",
        "Just checking on my case status. {name}, case #{case_num}. Haven't heard back in a while.",
        "Hey, any updates on case #{case_num}? This is {name}.",
        "Status update please? {name}, need to know where we are with my case."
    ]
    
    names = ["John Smith", "Sarah Johnson", "Mike Chen", "Lisa Brown", "David Martinez", 
             "Emily Davis", "James Wilson", "Maria Garcia", "Robert Taylor", "Jennifer Lee"]
    providers = ["Orlando Health", "Florida Hospital", "Dr. Patel", "Dr. Smith", "AdventHealth",
                 "Mayo Clinic", "Johns Hopkins", "Dr. Anderson", "Cleveland Clinic"]
    conditions = ["car accident injuries", "slip and fall", "workplace injury", "motorcycle accident",
                  "medical malpractice", "dog bite incident", "construction injury"]
    dates = ["May 15th", "last Tuesday", "June 3rd", "two weeks ago", "last month"]
    dobs = ["3/20/1985", "6/12/1990", "4/5/1978", "8/15/1982", "11/22/1975"]
    case_nums = ["12345", "67890", "11223", "44556", "77889"]
    appt_types = ["consultation", "follow-up", "initial meeting", "case review"]
    days = ["Monday", "next week", "Friday afternoon", "Tuesday morning"]
    
    import random
    
    messages = []
    for i in range(20):
        template = random.choice(templates)
        message = template.format(
            name=random.choice(names),
            provider=random.choice(providers),
            dob=random.choice(dobs),
            condition=random.choice(conditions),
            date=random.choice(dates),
            case_num=random.choice(case_nums),
            appt_type=random.choice(appt_types),
            day=random.choice(days)
        )
        messages.append(message)
    
    return jsonify({
        "count": len(messages),
        "messages": messages
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