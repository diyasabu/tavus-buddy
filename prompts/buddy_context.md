WHAT TAVUS SELLS
CVI, the Conversational Video Interface: an API for real-time, face-to-face AI video conversations. Customers build PALs and embed them in their apps. Common uses: AI SDRs, recruiters, qualification flows, support, onboarding, coaching.

WHAT A PAL IS
A PAL is what you build in CVI. It has a Face (how it looks), a Voice (how it sounds), a system prompt and context (how it thinks), and attached tools (what it can do). Pipeline mode "full" turns on perception, speech-to-text, LLM, text-to-speech, and rendering.

THE MODELS
Phoenix renders the face with full expression. Raven is perception: it lets the PAL see the user, read emotion and body language, and look at screen shares. Sparrow is turn-taking: it decides when the PAL speaks, with configurable patience and interruptibility.

TOOL CALLING
Tools live in a registry at /v2/tools, each with a name, description, JSON-schema parameters, and a delivery channel: an app message to the frontend or an HTTPS call to a backend. Tools are attached to a PAL at /v2/pals/{pal_id}/tools. on_call controls what the PAL says while a tool runs; on_resolve controls what it does with the result.

HOW THIS CALL WORKS UNDER THE HOOD
Your tools are delivered by API to a small Python service. create_pal calls POST /v2/pals with the user's answers. start_demo_conversation calls POST /v2/conversations and shows the link on a status page.

TEAM GLOSSARY
FDE: Forward Deployed Engineer, builds and ships PAL implementations with customers. CE: Customer Engineering, the team FDEs sit on. Implementation: a customer's deployment of one or more PALs. Time-to-first-value: how fast a new customer gets a working PAL; the CE team's favorite metric.

FIRST-WEEK READING, all at docs.tavus.io
1. CVI quickstart. 2. Tool Calling for LLM and Tool Delivery. 3. Perception (Raven). 4. Conversational Flow (Sparrow).
