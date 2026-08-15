import json
from datetime import datetime, date
from pathlib import Path
import yaml
from jinja2 import Environment, FileSystemLoader
import history


BASE_DIR = Path(__file__).parent

def load_template_config(path=None):
    path = path or BASE_DIR / "templates" / "default_template.yaml"
    with open(path) as f:
        return yaml.safe_load(f)

def build_prompt(items, config):
    lines = []
    for item in items:
        attention = item.needs_attention(config["stale_after_days"])
        if item.category == "awaiting_collection":
            detail = (
                f"awaiting collection at {item.collection_location}, "
                f"collect by {item.collection_deadline}"
            )
        else:
            detail = (
                f"last scanned {item.days_since_scan} day(s) ago at {item.last_scan_location}, "
                f"expected delivery window {item.expected_delivery_label or 'unknown'}"
            )
        lines.append(
            f"- Tracking {item.tracking_number}: category '{item.category}', "
            f"status '{item.status}', {detail}, flagged as needing attention: {attention}"
        )

    shipment_block = "\n".join(lines)
    system = (
            f"You write short, {config['tone']} shipment status updates for "
            f"{config['company_name']}'s daily tracking report. For each shipment, write one"
            " plain english sentence describing its status. For an in-transit item flagged as"
            " needing attention, say why in concrete terms (how long it has been stalled, or"
            " whether the expected delivery window has passed). For an awaiting_collection"
            " item, say where to collect it and the deadline, and only"
            " add urgency if it's flagged as needing attention. No filler like 'we hope this helps.'"
            " Then write one short headline summarizing the batch, mentioning how many need"
            " attention if any do. Respond as JSON only: "
            ' {"summary_headline": "...", "items": [{"tracking_number": "...", '
            '"narrative": "..."}]}'
    )
    return system, shipment_block

def _strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.removesuffix("```")
        text = text.strip()
    return text

def call_claude(system_prompt, shipment_block):
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": shipment_block}],
    )
    return json.loads(_strip_code_fence(response.content[0].text))

def _prepare_render_context(items, config, narrative):
    stats = {"delivered": 0, "in_transit": 0, "awaiting_collection": 0, "needs_attention": 0}
    narrative_by_number = {n["tracking_number"]: n["narrative"] for n in narrative["items"]}
    rendered_items = []

    for item in items:
        attention = item.needs_attention(config["stale_after_days"])
        if item.category == "delivered":
            stats["delivered"] += 1
            bg, fg, label = config["brand"]["delivered_bg"], config["brand"]["delivered_color"], "delivered"
        elif attention:
            stats["needs_attention"] += 1
            bg, fg, label = config["brand"]["attention_bg"], config["brand"]["attention_color"], "needs attention"
        elif item.category == "awaiting_collection":
            stats["awaiting_collection"] += 1
            bg, fg, label = config["brand"]["collection_bg"], config["brand"]["collection_color"], "awaiting collection"
        else:
            stats["in_transit"] += 1
            bg, fg, label = config["brand"]["in_transit_bg"], config["brand"]["in_transit_color"], "in transit"

        rendered_items.append({
              "tracking_number": item.tracking_number,
              "status_label": label,
              "badge_bg": bg,
              "badge_text": fg,
              "narrative": narrative_by_number.get(item.tracking_number)
        })

    return {
        "report_title": config["report_title"],
        "report_date": datetime.now().strftime("%A, %-d %B"),
        "summary_headline": narrative["summary_headline"],
        "stats": [
            {"label": "Delivered", "count": stats["delivered"], "color": config["brand"]["delivered_color"]},
            {"label": "In transit", "count": stats["in_transit"], "color": config["brand"]["in_transit_color"]},
            {"label": "Awaiting collection", "count": stats["awaiting_collection"], "color": config["brand"]["collection_color"]},
            {"label": "Needs attention", "count": stats["needs_attention"], "color": config["brand"]["attention_color"]},
        ],
       "items": rendered_items,
    }

def _render(items, config, narrative, template_name):
    context = _prepare_render_context(items, config, narrative)
    env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))
    template = env.get_template(template_name)
    return template.render(**context)

def _render_report(items, config, narrative):
    """
    Email safe version: table layout, inline styles for actual sending
    """
    return _render(items, config, narrative, "report_email.html")

def render_pdf_report(items, config, narrative):
    """
    Print pdf doc: @page setup, page break control, and adds modern CSS
    """
    return _render(items, config, narrative, "report_pdf.html")

def log_report(items, config, log_path=None):
    """
    Appends today's flagged state to a local history file.
    Nothing reads this yet - it exists so a future weekly digest or trend
    view has real data to work with from day 1
    """
    log_path = log_path or BASE_DIR / "report_history.jsonl"
    entry = {
        "date": date.today().isoformat(),
        "items": [
            {
                "tracking_number": i.tracking_number,
                "status": i.status,
                "category": i.category,
                "needs_attention": i.needs_attention(config["stale_after_days"]),
                "days_since_scan": i.days_since_scan,
            }
            for i in items
        ],
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

def generate_report(items, template_path=None):
    config = load_template_config(template_path)
    items = history.filter_dropped_items(items, config.get("drop_after_days", 3))
    system_prompt, shipment_block = build_prompt(items, config)
    narrative = call_claude(system_prompt, shipment_block)
    log_report(items, config)
    return _render_report(items, config, narrative)

def generate_pdf_report(items, template_path=None):
    config = load_template_config(template_path)
    items = history.filter_dropped_items(items, config.get("drop_after_days", 3))
    system_prompt, shipment_block = build_prompt(items, config)
    narrative = call_claude(system_prompt, shipment_block)
    log_report(items, config)
    return render_pdf_report(items, config, narrative)
