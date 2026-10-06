import os
import json
import re
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

MOCK_GEMINI = os.getenv("MOCK_GEMINI", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# "-latest" alias tracks the current Flash model, so a model retirement doesn't break planning
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

async def plan_browser_flow(url: str, session_flow: str) -> list[dict]:
    """
    Translates a natural language session_flow description into a list of structured browser actions.
    If Gemini API key is missing or mock mode is enabled, it falls back to a deterministic parser.
    """
    logger.info(f"Planning flow for {url} with description: '{session_flow}'")
    
    if MOCK_GEMINI or not GEMINI_API_KEY or "mock" in GEMINI_API_KEY:
        logger.info("Using deterministic fallback parser for planner (mock mode)")
        return _fallback_planner(url, session_flow)
        
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        prompt = f"""
You are a web automation planner. Translate the following natural language description of web browsing actions into a structured JSON list of steps for Playwright.
The base URL of the site is: {url}

User Flow Description:
"{session_flow}"

You must output ONLY a valid JSON array of objects. Do not include markdown code block formatting (like ```json).
Each object must have an "action" field, and appropriate additional parameters:
- For "navigate": {{"action": "navigate", "url": "URL"}} (if the URL is relative like '/about', combine it with the base URL '{url}')
- For "click": {{"action": "click", "selector": "CSS selector or text search like 'text=Login' or 'button'"}}
- For "fill": {{"action": "fill", "selector": "CSS selector or 'input[type=email]'", "value": "text to enter"}}
- For "scroll": {{"action": "scroll", "direction": "down" or "up", "amount": pixels_to_scroll_integer}}

Example:
[
  {{"action": "navigate", "url": "{url}"}},
  {{"action": "click", "selector": "text=Get Started"}},
  {{"action": "scroll", "direction": "down", "amount": 500}}
]
"""
        llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY)
        response = await llm.ainvoke(prompt)
        text = response.text.strip()
        
        # Clean any markdown block formatting if Gemini ignored the instruction
        if text.startswith("```"):
            # Strip first line and last line
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        plan = json.loads(text)
        logger.info(f"Gemini planned {len(plan)} actions successfully.")
        return plan

    except Exception as e:
        logger.error(f"Gemini planning failed: {e}. Falling back to deterministic planner.")
        return _fallback_planner(url, session_flow)

def _fallback_planner(base_url: str, session_flow: str) -> list[dict]:
    """
    A simple rule-based parser that splits sentences/lines and matches keywords.
    """
    if not session_flow:
        # Default fallback
        return [{"action": "navigate", "url": base_url}]

    # Normalize base_url
    base_url = base_url.rstrip("/")

    steps = []
    # Split description by lines or periods/semicolons
    parts = re.split(r'[\r\n\.;]+', session_flow)
    
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
            
        # 1. Match navigate
        if "navigate" in part or "go to" in part or "open" in part:
            # Check for path (e.g., /about or /login)
            path_match = re.search(r'(/[a-zA-Z0-9_\-\/]*)', part)
            if path_match:
                path = path_match.group(1)
                steps.append({"action": "navigate", "url": f"{base_url}{path}"})
            else:
                # Fallback to base url
                steps.append({"action": "navigate", "url": base_url})
                
        # 2. Match click
        elif "click" in part:
            # Look for button names or links
            # e.g., click "login" -> text=login
            quote_match = re.search(r'["\']([^"\']+)["\']', part)
            if quote_match:
                btn_text = quote_match.group(1)
                steps.append({"action": "click", "selector": f"text={btn_text}"})
            else:
                # Try simple keyword extraction after "click"
                after_click = part.split("click")[-1].strip()
                # strip articles
                after_click = re.sub(r'^(the|a|an|button|link)\s+', '', after_click)
                if after_click:
                    steps.append({"action": "click", "selector": f"text={after_click}"})
                else:
                    steps.append({"action": "click", "selector": "button"})
                    
        # 3. Match fill
        elif "fill" in part or "type" in part or "enter" in part:
            quote_match = re.findall(r'["\']([^"\']+)["\']', part)
            if len(quote_match) >= 1:
                # If they specify value, e.g., fill "test@example.com"
                value = quote_match[0]
                # Default selector for inputs
                selector = "input[type=text]"
                if "email" in part:
                    selector = "input[type=email]"
                elif "password" in part:
                    selector = "input[type=password]"
                steps.append({"action": "fill", "selector": selector, "value": value})
            else:
                steps.append({"action": "fill", "selector": "input", "value": "test"})

        # 4. Match scroll
        elif "scroll" in part:
            direction = "down"
            if "up" in part:
                direction = "up"
            # look for number of pixels
            num_match = re.search(r'(\d+)', part)
            amount = int(num_match.group(1)) if num_match else 500
            steps.append({"action": "scroll", "direction": direction, "amount": amount})

    # Always ensure we have at least navigation to the base URL at the beginning
    if not steps or steps[0].get("action") != "navigate":
        steps.insert(0, {"action": "navigate", "url": base_url})

    return steps
