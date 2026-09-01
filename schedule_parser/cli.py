"""
Command-line interface for SYNAPSE Schedule Parser.
Usage:
  python -m schedule_parser.cli parse data/schedule.csv --show-quality
  python -m schedule_parser.cli detect tests/fixtures/sample_primavera.xer
  python -m schedule_parser.cli audit data/schedule.csv
"""

import argparse
import json
import sys
from typing import Optional

from .pipeline import ScheduleParser
from .detector import detect_format


def main(args: Optional[list] = None):
    parser = argparse.ArgumentParser(
        prog="python -m schedule_parser.cli",
        description="SYNAPSE Primavera / MS Project Schedule Parser & Quality Auditor (Yazeen's Module)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: parse
    parse_cmd = subparsers.add_parser("parse", help="Parse a schedule export file")
    parse_cmd.add_argument("file", help="Path to schedule file (CSV, XER, XML, JSON)")
    parse_cmd.add_argument("--format", help="Override format detection (primavera_xer, msproject_xml, etc.)")
    parse_cmd.add_argument("-o", "--output", help="Output file path for parsed JSON activities")
    parse_cmd.add_argument("-r", "--report", help="Output file path for data-quality report JSON")
    parse_cmd.add_argument("--target", choices=["contract", "amritha"], default="contract", help="Output schema format")
    parse_cmd.add_argument("--show-quality", action="store_true", help="Print data quality issue summary")
    parse_cmd.add_argument("--limit", type=int, default=10, help="Number of activities to preview in console")

    # Command: audit
    audit_cmd = subparsers.add_parser("audit", help="Audit schedule data quality without full export")
    audit_cmd.add_argument("file", help="Path to schedule file to audit")

    # Command: detect
    detect_cmd = subparsers.add_parser("detect", help="Detect file format")
    detect_cmd.add_argument("file", help="Path to schedule file")

    parsed_args = parser.parse_args(args)

    if not parsed_args.command:
        parser.print_help()
        sys.exit(1)

    schedule_parser = ScheduleParser()

    if parsed_args.command == "detect":
        fmt, reason = detect_format(parsed_args.file)
        print(f"\n[SYNAPSE Format Detection]")
        print(f"  File:     {parsed_args.file}")
        print(f"  Format:   {fmt}")
        print(f"  Evidence: {reason}\n")
        return

    elif parsed_args.command == "audit":
        res = schedule_parser.parse(parsed_args.file)
        print(f"\n[SYNAPSE Schedule Quality Audit]")
        print(f"  File:                {parsed_args.file}")
        print(f"  Detected Format:     {res.format_detected}")
        print(f"  Inspected Records:   {res.quality_report.total_records_inspected}")
        print(f"  Total Issues:        {res.quality_report.total_issues}")
        print(f"    - Errors:          {res.quality_report.error_count}")
        print(f"    - Warnings:        {res.quality_report.warning_count}")
        print(f"    - Info/Notices:    {res.quality_report.info_count}")

        if res.quality_report.issues:
            print("\n  Issues Breakdown:")
            for issue in res.quality_report.issues:
                prefix = f"[{issue.severity.value}]"
                print(f"    {prefix:<10} {issue.issue_type:<20} Activity: {issue.activity_id or 'N/A':<12} {issue.message}")
        else:
            print("\n  ✓ 100% clean schedule — No quality issues detected!")
        print()
        return

    elif parsed_args.command == "parse":
        res = schedule_parser.parse(parsed_args.file, format_hint=parsed_args.format)
        activities = (
            res.to_amritha_format() if parsed_args.target == "amritha" else res.to_contract_format()
        )

        print(f"\n=======================================================")
        print(f" SYNAPSE Schedule Parser — Yazeen's Module")
        print(f"=======================================================")
        print(f" File:                 {parsed_args.file}")
        print(f" Detected Format:      {res.format_detected}")
        print(f" Parse Time:           {res.parse_time_ms:.2f} ms")
        print(f" Total Activities Read:{res.total_activities_read}")
        print(f" L5/L6 Activities:     {res.l5_l6_activities_count}")
        print(f" Summary Nodes Filtered:{res.filtered_summary_count}")
        print(f" WBS Nodes Built:      {len(res.wbs_nodes)}")
        print(f" Quality Errors:       {res.quality_report.error_count}")
        print(f" Quality Warnings:     {res.quality_report.warning_count}")
        print(f" Status:               {'VALID (Ready for Amritha)' if res.is_valid else 'FAILED (Blocking Errors)'}")
        print(f"=======================================================\n")

        # Preview activities
        preview_count = min(parsed_args.limit, len(activities))
        print(f"Preview of first {preview_count} standardized activities:")
        print(f"{'ID':<12} {'Discipline':<15} {'Dates':<24} {'Activity Name'}")
        print("-" * 75)
        for act in activities[:preview_count]:
            dates = f"{act.get('planned_start', '')} -> {act.get('planned_finish', '')}"
            disc = act.get("discipline") or "N/A"
            name = act.get("activity_name", "")
            if len(name) > 30:
                name = name[:27] + "..."
            print(f"{act.get('activity_id', ''):<12} {disc:<15} {dates:<24} {name}")
        print("-" * 75)

        if parsed_args.show_quality and res.quality_report.issues:
            print("\nQuality Findings:")
            for issue in res.quality_report.issues[:15]:
                print(f"  [{issue.severity.value}] {issue.issue_type}: {issue.message}")
            if len(res.quality_report.issues) > 15:
                print(f"  ... and {len(res.quality_report.issues) - 15} more issues.")

        # Save output if requested
        if parsed_args.output:
            with open(parsed_args.output, "w", encoding="utf-8") as f:
                json.dump(activities, f, indent=2)
            print(f"\n✓ Saved {len(activities)} activities to {parsed_args.output}")

        if parsed_args.report:
            with open(parsed_args.report, "w", encoding="utf-8") as f:
                json.dump(res.quality_report.model_dump(), f, indent=2)
            print(f"✓ Saved quality audit report to {parsed_args.report}")
        print()


if __name__ == "__main__":
    main()
