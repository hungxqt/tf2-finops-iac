"""Generate docs/statemachine.json from the template with real ARNs substituted."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "modules", "orchestration", "statemachine.json")
OUTPUT = os.path.join(ROOT, "docs", "statemachine.json")
FEEDBACK_TEMPLATE = os.path.join(ROOT, "modules", "orchestration", "feedback_statemachine.json")
FEEDBACK_OUTPUT = os.path.join(ROOT, "docs", "feedback-statemachine.json")

replacements = [
    ("${state_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-state"),
    ("${vpc_alb_caller_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"),
    ("${audit_writer_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-audit_writer"),
    ("${normalizer_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-normalizer"),
    ("${cost_puller_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-cost_puller"),
    ("${containment_worker_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-containment_worker"),
    ("${router_lambda_arn}", "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-router"),
    ("${account_policy_table_name}", "tf2-finops-sandbox-account-policy"),
    ("${rollback_cache_table_name}", "tf2-finops-sandbox-rollback-cache"),
    ("${rollback_status_queue_url}", "https://sqs.ap-southeast-1.amazonaws.com/123456789012/tf2-finops-sandbox-rollback-status"),
    ("${finance_alerts_sns_topic_arn}", "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-sandbox-finance-alerts"),
    ("${engineering_alerts_sns_topic_arn}", "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-sandbox-engineering-alerts"),
    ("${cur_retry_interval_seconds}", "3600"),
    ("${ai_engine_contract_version}", "v1"),
]

for template_path, output_path in [
    (TEMPLATE, OUTPUT),
    (FEEDBACK_TEMPLATE, FEEDBACK_OUTPUT),
]:
    with open(template_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    for line in lines:
        for old, new in replacements:
            line = line.replace(old, new)
        out.append(line)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.writelines(out)

    with open(output_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    print(f"{os.path.relpath(output_path, ROOT)} states ({len(doc['States'])}): {list(doc['States'].keys())[:6]} ...")
print("Done")
