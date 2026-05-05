# Observability Demo: Prometheus & Grafana in Action

**Target Audience:** Non-technical / mixed (seeing these tools for the first time)
**Duration:** 5-10 minutes
**Goal:** Leave a "Wow" impression by showing how quickly we can go from a portfolio-wide view down to the exact failing line of code/query during an incident.

---

## 1. The Hook: "The 30,000 Foot View" (Overview Dashboard)
*Open `Application Portfolio Overview` dashboard*

**Talking Track:**
"Welcome to our new mission control. When an executive or a site reliability engineer logs in at 9 AM, they don't want to dig through logs. They want one question answered: *Is everything okay?*"

*   **Highlight the UI:** "Here we have all our critical business applications—Web Apps on top, APIs below. The design gives us an instant pulse. Green 'UP' badges mean we're healthy."
*   **Highlight the Bottom Panel:** "If something *is* failing, this bottom 'Worst First' panel automatically sorts the bleeding applications to the top. We don't hunt for problems; the dashboard brings the problems to us."

**Action:**
Point out an application that currently has an uptime below 100% or is showing a yellow/red status. Click on its "Open Analytics →" link.

---

## 2. The Golden Signals (6-Layer Observability Dashboard)
*You are now on the 6-Layer dashboard for the selected app*

**Talking Track:**
"Clicking an app brings us from 30,000 feet down to 10,000 feet. This is our 6-Layer Observability view. The very first layer is what Google calls the 'Four Golden Signals' — Latency, Traffic, Errors, and Saturation."

*   **Traffic (Top Right):** "This is our heartbeat. How many users are hitting the system right now."
*   **Errors (Bottom Left):** "Are those users getting what they asked for, or are they getting 500 server errors?"
*   **Saturation (Bottom Right):** "This is our resource usage—CPU, Memory, and Database connections. We combined these into one panel so we can instantly see if the server is choking."
*   **Latency (Top Left):** "And this is the most important one: Latency. Notice the **p99 line** (the red line). We don't just look at averages. An average hides pain. The 99th percentile tells us what the absolute worst experience is for our 1% of unluckiest users."

---

## 3. The Incident Drill-Down (The "Aha!" Moment)
**Talking Track:**
"Let's say we get an alert. It might be users complaining about 500 errors, or it might be complaints that the app is crawling to a halt. In the old days, this meant a war room, 5 engineers, and 3 hours of guessing. Let me show you what it looks like today."

**Action Sequence:**
1.  **Spot the Spike:** Look at Layer 1 and find a spike on *either* the **Error Count** chart OR the **Request Latency** chart.
2.  **The Drill-Down:** "Instead of guessing what's broken, I'm just going to ask Grafana." Click directly on the spike you found. This opens either the **Error Drilldown Table** or **Performance Drilldown Table** at the bottom of the screen.
3.  **Identify the Culprit:** "Instantly, Grafana tells us exactly *which* endpoint is failing or slowing down. It's not the whole app—it's specifically the `/api/checkout` (or whichever endpoint is top of the list) operation that is causing the problem."

---

## 4. The Deep Dive (Layer 5: Database & Storage)
**Talking Track:**
"We know *what* is failing, but *why*? Let's check the infrastructure layers."

**Action Sequence:**
1.  Expand **Layer 5 — Database & Storage**.
2.  Point to the **DB Query Latency** and **Lock Waits** charts.
3.  "Because Prometheus pulls metrics from everything—not just our code, but our databases too—we can see that right when the checkout API failed, we had a massive spike in Database Lock Waits. Two transactions were fighting for the same row in the database."

---

## 5. The Conclusion
**Talking Track:**
"What you just saw took us less than two minutes. We went from a portfolio-wide green/red light, down to a specific application, identified the exact user journey that was failing in the drilldown table, and proved it was a backend issue. 

This isn't just monitoring. It's observability. It gives our engineering teams their time back, and gets our users back online faster."
