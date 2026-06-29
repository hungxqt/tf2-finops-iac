import json

def main():
    template_path = "modules/orchestration/statemachine.json"
    dest_path = "docs/statemachine.json"
    feedback_template_path = "modules/orchestration/feedback_statemachine.json"
    feedback_dest_path = "docs/feedback-statemachine.json"
    
    replacements = {
        "${state_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-state",
        "${cost_puller_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-cost_puller",
        "${normalizer_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-normalizer",
        "${vpc_alb_caller_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller",
        "${router_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-router",
        "${audit_writer_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-audit_writer",
        "${containment_worker_lambda_arn}": "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-containment_worker",
        "${finance_alerts_sns_topic_arn}": "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-sandbox-finance-alerts",
        "${engineering_alerts_sns_topic_arn}": "arn:aws:sns:ap-southeast-1:123456789012:tf2-finops-sandbox-engineering-alerts",
        "${account_policy_table_name}": "tf2-finops-sandbox-account-policy",
        "${results_table_name}": "tf2-finops-sandbox-ai-results",
        "${rollback_cache_table_name}": "tf2-finops-sandbox-rollback-cache",
        "${rollback_status_queue_url}": "https://sqs.ap-southeast-1.amazonaws.com/123456789012/tf2-finops-sandbox-rollback-status",
        "${ai_engine_contract_version}": "v1",
        "${ai_poll_max_attempts}": "6",
        "${ai_poll_interval_seconds}": "10",
        "${cur_retry_interval_seconds}": "3600"
    }

    for source_path, output_path in [
        (template_path, dest_path),
        (feedback_template_path, feedback_dest_path),
    ]:
        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()

        for k, v in replacements.items():
            content = content.replace(k, v)

        json.loads(content)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    print("Success: JSON is valid after substitutions")

if __name__ == "__main__":
    main()
