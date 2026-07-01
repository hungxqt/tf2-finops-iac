- Trust policy

```json

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowAssumeFromCostPullerRoles",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::093490087544:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "aws:RequestTag/tenant_id": [
                        "e70bb442-35fe-5b66-a05e-c4b6d438363f",
                        "tenant-synthetic"
                    ]
                },
                "ArnEquals": {
                    "aws:PrincipalArn": [
                        "arn:aws:iam::093490087544:role/tf2-finops-sandbox-cost_puller-role",
                        "arn:aws:iam::093490087544:role/tf2-finops-staging-cost_puller-role",
                        "arn:aws:iam::093490087544:role/tf2-finops-prod-cost_puller-role"
                    ]
                }
            }
        },
        {
            "Sid": "AllowTenantSessionTag",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::093490087544:root"
            },
            "Action": "sts:TagSession",
            "Condition": {
                "StringEquals": {
                    "aws:RequestTag/tenant_id": [
                        "e70bb442-35fe-5b66-a05e-c4b6d438363f",
                        "tenant-synthetic"
                    ]
                },
                "ForAllValues:StringEquals": {
                    "aws:TagKeys": "tenant_id"
                },
                "ArnEquals": {
                    "aws:PrincipalArn": [
                        "arn:aws:iam::093490087544:role/tf2-finops-sandbox-cost_puller-role",
                        "arn:aws:iam::093490087544:role/tf2-finops-staging-cost_puller-role",
                        "arn:aws:iam::093490087544:role/tf2-finops-prod-cost_puller-role"
                    ]
                }
            }
        }
    ]
}

```

- Inline permission policy

```json

  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowMemberCostExplorerAndMetrics",
        "Effect": "Allow",
        "Action": [
          "ce:GetCostAndUsage",
          "cloudwatch:GetMetricData"
        ],
        "Resource": "*"
      }
    ]
  }

```