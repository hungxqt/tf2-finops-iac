#!/usr/bin/env python3
"""Find and optionally quarantine malformed curated Parquet objects.

The normalizer used to fall back to JSON bytes while keeping a .parquet suffix.
Those objects break Athena with HIVE_BAD_DATA. This script is dry-run by default.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import boto3


def iter_objects(s3, bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("_curated.parquet"):
                yield key, obj


def is_parquet(s3, bucket: str, key: str) -> bool:
    head = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-3")
    return head["Body"].read() == b"PAR1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="cost/curated/")
    parser.add_argument("--quarantine-prefix", default="quarantine/malformed-curated/")
    parser.add_argument("--apply", action="store_true", help="Copy malformed objects to quarantine and delete the originals")
    args = parser.parse_args()

    s3 = boto3.client("s3")
    checked = 0
    malformed = 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for key, obj in iter_objects(s3, args.bucket, args.prefix):
        checked += 1
        if is_parquet(s3, args.bucket, key):
            continue

        malformed += 1
        quarantine_key = f"{args.quarantine_prefix.rstrip('/')}/{stamp}/{key}"
        print(f"[malformed] s3://{args.bucket}/{key} size={obj['Size']}")
        if args.apply:
            s3.copy_object(
                Bucket=args.bucket,
                Key=quarantine_key,
                CopySource={"Bucket": args.bucket, "Key": key},
                MetadataDirective="COPY",
            )
            s3.delete_object(Bucket=args.bucket, Key=key)
            print(f"[quarantined] s3://{args.bucket}/{quarantine_key}")

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"[summary] mode={mode} checked={checked} malformed={malformed}")
    return 1 if malformed and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
