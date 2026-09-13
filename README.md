# FoodBridge — AI-Driven Surplus Food Redistribution & Intelligent Logistics

FoodBridge is an intelligent food redistribution platform designed to connect **food donors, NGOs, and volunteers** through an integrated AI-powered workflow.

The platform combines **food quality/risk assessment, demand forecasting, NGO matching, expiry-aware routing, Google Maps, real-time GPS tracking, WebSockets, receipt verification, feedback, and multilingual AI assistance** into a single end-to-end system.

The objective is to reduce food wastage while improving the speed, reliability, and transparency of surplus-food redistribution.

---

## 🌐 Repository

**GitHub Repository**

https://github.com/Varunpv2005/FoodBridge-Final

---

# 📌 Table of Contents

- [Overview](#-overview)
- [Problem Statement](#-problem-statement)
- [Objectives](#-objectives)
- [Key Features](#-key-features)
- [End-to-End Workflow](#-end-to-end-workflow)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [AI and ML Components](#-ai-and-ml-components)
- [Food Risk Assessment](#-food-risk-assessment)
- [Demand Forecasting](#-demand-forecasting)
- [NGO Matching](#-ngo-matching)
- [Expiry-Aware Routing](#-expiry-aware-routing)
- [Real-Time GPS Tracking](#-real-time-gps-tracking)
- [WebSocket Architecture](#-websocket-architecture)
- [Google Maps and Google Routes](#-google-maps-and-google-routes)
- [Role-Based Dashboards](#-role-based-dashboards)
- [AI Assistant](#-ai-assistant)
- [Receipt Verification and Feedback](#-receipt-verification-and-feedback)
- [Security](#-security)
- [Project Structure](#-project-structure)
- [Database](#-database)
- [Environment Configuration](#-environment-configuration)
- [Local Installation](#-local-installation)
- [Running the Application](#-running-the-application)
- [Running Tests](#-running-tests)
- [Frontend Build](#-frontend-build)
- [Docker](#-docker)
- [Evaluation](#-evaluation)
- [Research and Experimental Results](#-research-and-experimental-results)
- [Limitations](#-limitations)
- [Future Enhancements](#-future-enhancements)
- [Important Notes](#-important-notes)
- [Contributors](#-contributors)
- [License](#-license)

---

# 🚀 Overview

FoodBridge addresses the problem of surplus food going to waste while nearby communities and NGOs may have unmet food requirements.

The platform coordinates the complete redistribution lifecycle:

```text
DONOR
  │
  │ Create Food Donation
  ▼
AI FOOD ASSESSMENT
  │
  ├── Image / Quality Assessment
  ├── Food Risk Estimation
  └── Degradation / Freshness Estimation
  │
  ▼
NGO MATCHING
  │
  ├── Distance
  ├── Capacity
  ├── Food Compatibility
  ├── Freshness / Safety
  └── Other contextual factors
  │
  ▼
NGO ACCEPTANCE
  │
  ▼
VOLUNTEER ASSIGNMENT
  │
  ▼
EXPIRY-AWARE ROUTING
  │
  ├── Google Routes
  ├── Route Geometry
  ├── Distance
  ├── ETA
  └── Degradation / lateness penalty
  │
  ▼
LIVE DELIVERY
  │
  ├── Real GPS
  ├── WebSocket Updates
  ├── Google Maps
  └── Cross-role Synchronization
  │
  ▼
DELIVERY COMPLETION
  │
  ▼
NGO RECEIPT VERIFICATION
  │
  ▼
FEEDBACK / IMPACT
