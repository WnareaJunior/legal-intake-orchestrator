# **AI Legal Tender (Hackathon Prototype) — Multi-Agent Intake Orchestration**

**Problem:** Large firms like Morgan & Morgan process 10,000+ monthly client inquiries. Each one typically requires ~15 minutes of paralegal time for classification, validation, and draft generation.

**Goal:** Build a **working prototype** of an autonomous multi-agent system that handles complex legal intake at scale with built-in quality safeguards.

---

## **Key Features (Prototype)**

### 🤖 **Multi-Agent Workflow Orchestration**

* **RecordsWrangler Agent** – Generates HIPAA-compliant medical records requests
* **Scheduling Agent** – Coordinates intake appointments
* **Status Agent** – Handles case status inquiries

### 🎯 **Multi-Provider Detection**

Automatically identifies when multiple providers are mentioned:

* Detects 3–7+ providers in a single inquiry
* Generates individualized, provider-specific request drafts
* Maintains timelines + incident context across requests

### ✅ **Quality Guardian Layer**

* Confidence scoring (≥85% threshold required)
* Critical field validation before approval
* Auto-retry with structured feedback
* System halts output if quality drops below threshold

### ⚡ **Parallel Batch Processing**

* Processes 20+ inquiries concurrently
* ~0.5 messages/second including validation
* ~428× faster vs. manual processing

---

## **Tech Stack (Hackathon Build)**

| Layer        | Tools                                                     |
| ------------ | --------------------------------------------------------- |
| Backend      | Python + Flask                                            |
| AI Model     | **Google Gemini 2.5 Flash**                               |
| Frontend     | React + Tailwind CSS                                      |
| Architecture | Autonomous multi-agent orchestration + quality validation |

---

## **Demo Highlights**

* Single medical records request: **~3 seconds**
* Complex case (5 providers): **~5 seconds**
* Bulk batch (20 inquiries): **~40 seconds** with validation

---

## **Results (Projected)**

* **Time Saved:** ~428× faster than manual workflows
* **Quality:** Maintains ≥85% approval confidence
* **Scale:** Handles ~10k monthly inquiries in ~5.5 compute hours
