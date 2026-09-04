# FoodBridge

### An Intelligent AI-Driven Platform for Surplus Food Redistribution, Demand Forecasting, and Expiry-Aware Logistics

FoodBridge is a real-time food donation redistribution platform designed to reduce food wastage by intelligently connecting food donors with NGOs and volunteers.

The platform combines food-risk estimation, intelligent donor-NGO matching, expiry-aware logistics, volunteer allocation, real-time GPS tracking, demand forecasting, and an AI-powered conversational assistant into a unified system.

---

## 📌 Project Overview

Large quantities of surplus food from restaurants, events, institutions, households, and other sources are discarded because suitable recipients and transportation cannot always be identified within the food's safe consumption window.

FoodBridge addresses this problem through an integrated digital platform that coordinates:

**Donor → NGO → Volunteer → Delivery**

The system evaluates donated food, identifies suitable NGOs, recommends the most appropriate recipient, automatically assigns an eligible volunteer after NGO acceptance, and tracks the delivery using real-time GPS.

---

## 🎯 Objectives

The major objectives of FoodBridge are:

- Reduce surplus food wastage.
- Connect food donors with suitable NGOs in real time.
- Estimate food spoilage and risk using software-based analysis.
- Consider food quantity, compatibility, urgency, capacity, and distance during matching.
- Automatically allocate suitable volunteers after NGO acceptance.
- Optimize delivery routes using real road-network information.
- Track active deliveries using real-time GPS.
- Detect route deviations during delivery.
- Support demand forecasting for future planning.
- Provide multilingual and conversational assistance.
- Provide administrators with system monitoring and evaluation tools.

---

## ✨ Key Features

### 1. Donor Management

Donors can:

- Create food donation requests.
- Enter food type and quantity.
- Specify preparation/cooking time.
- Select pickup location.
- Upload food images.
- View food safety/risk information.
- Track donation status.
- Track assigned volunteers.
- Monitor delivery progress in real time.

---

### 2. Food Risk Estimation

FoodBridge evaluates donated food using software-based food-risk estimation.

The system considers factors such as:

- Food type
- Quantity
- Time since preparation
- Safe consumption window
- Available food information
- Risk-related characteristics

The result is presented as a food-risk score with supporting factors.

---

### 3. Intelligent NGO Matching

Instead of automatically assigning a donation to an NGO, FoodBridge recommends the most suitable NGO.

The matching process considers:

- Geographic distance
- Estimated travel time
- NGO capacity
- Food compatibility
- Donation urgency
- Food-risk/safe-window constraints
- Matching model score
- NGO feedback information

The selected NGO receives a request and can verify the donation before accepting it.

### NGO Workflow

```text
Donation Created
       ↓
Suitable NGO Recommended
       ↓
NGO Request Sent
       ↓
NGO Verifies Donation
       ↓
   ┌───────────────┐
   │               │
Accept           Reject
   │               │
   ↓               ↓
Volunteer       Next suitable
Allocation       NGO Request
