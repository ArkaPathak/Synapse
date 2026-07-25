"""
Run once to generate data/incidents.json — a realistic ServiceNow-style
incident dataset: 24 closed historical incidents (Synapse's knowledge base)
plus 6 active incidents (today's queue) for the live demo.

    python seed_incidents.py
"""
import json
import os

CLOSED = [
    # (short_description, description, category, priority, assignment_group,
    #  opened_at, resolved_at, opened_by, resolved_by, root_cause, close_notes)
    ("No sales records for store 1134 (Chicago region)",
     "Store 1134 in the Chicago region shows zero sales records in the enhanced dataset for the previous business day.",
     "Data Pipeline Failure", "P2", "Data Platform Support",
     "2024-03-02T06:40:00Z", "2024-03-02T11:15:00Z", "monitoring-bot", "R. Sharma",
     "The upstream POS feed for the Chicago region uses a two-digit year field, and a leap-year date rollover caused the extract job to skip records for stores in that region.",
     "Manually re-pulled the missing day's file from the upstream SFTP drop, patched the date field, and re-ran ingestion for the affected store range."),

    ("Loyalty transactions missing for Midwest store batch",
     "Loyalty point transactions for a batch of Midwest stores are absent from the enhanced dataset for one business day.",
     "Data Pipeline Failure", "P2", "Data Platform Support",
     "2024-03-05T07:05:00Z", "2024-03-05T10:30:00Z", "monitoring-bot", "R. Sharma",
     "Same leap-year date handling defect in the upstream POS extract as seen with Chicago-region stores days earlier.",
     "Applied the known leap-year patch script to the affected date range and re-triggered the loyalty ingestion job."),

    ("SSIS_LoadStoreMaster fails with Error 402",
     "Nightly staging load job SSIS_LoadStoreMaster fails partway through execution with Error 402.",
     "Application Error", "P1", "App Engineering L2",
     "2024-05-14T02:15:00Z", "2024-05-14T07:00:00Z", "job-scheduler", "A. Banerjee",
     "Error 402 traced to the staging table's identity column reaching its allowed value ceiling after months of accumulated test inserts were never purged.",
     "Reseeded the identity column after archiving old staging rows, and added a monthly staging-table cleanup step to the job."),

    ("ETL_EnhanceProductRef fails after upstream release",
     "Job ETL_EnhanceProductRef fails immediately after an upstream vendor system's scheduled maintenance window, with a column-not-found error.",
     "Application Error", "P2", "App Engineering L2",
     "2024-06-01T04:20:00Z", "2024-06-01T09:10:00Z", "job-scheduler", "A. Banerjee",
     "The upstream system renamed a source column during their maintenance release without prior notice, breaking the mapping in the ETL package.",
     "Updated the column mapping to the new source column name and requested advance notice of schema changes for future upstream releases."),

    ("Two more jobs fail same morning as ETL_EnhanceProductRef",
     "ETL_LoadSupplierRef and ETL_LoadPricingRef both fail within the same hour, the same morning as the ETL_EnhanceProductRef failure.",
     "Application Error", "P2", "App Engineering L2",
     "2024-06-01T04:45:00Z", "2024-06-01T09:40:00Z", "job-scheduler", "A. Banerjee",
     "The same upstream maintenance release renamed a shared reference column used by all three packages.",
     "Applied the same column-mapping fix pattern across all three affected packages in one pass instead of troubleshooting each separately."),

    ("Update mailing address on file for store 2210",
     "Business team requests correcting an outdated mailing address on file for store 2210 after a franchise ownership change.",
     "Data Correction Request", "P3", "Data Governance",
     "2024-07-10T13:00:00Z", "2024-07-10T15:30:00Z", "business-portal", "P. Das",
     "Standard data correction request; source record had not been refreshed since a franchise transfer.",
     "Updated the reference record per the business-approved change form and confirmed downstream propagation."),

    ("Update holiday operating hours for store group",
     "A group of stores need updated holiday operating hours reflected in the reference data ahead of a public holiday.",
     "Data Correction Request", "P4", "Data Governance",
     "2024-11-20T09:00:00Z", "2024-11-20T11:00:00Z", "business-portal", "P. Das",
     "Routine seasonal update request, no defect.",
     "Bulk-updated operating hours for the specified store list using the standard reference-data update template."),

    ("Retrigger failed batch — BatchTag mismatch",
     "A batch of roughly 150 records failed to load due to a BatchTag mismatch and need to be retriggered.",
     "Batch Reprocessing", "P2", "Data Platform Support",
     "2024-08-02T10:10:00Z", "2024-08-02T12:45:00Z", "monitoring-bot", "S. Iyer",
     "The BatchTag on the source file did not match the expected format after a manual upstream correction.",
     "Corrected the BatchTag field and retriggered the affected record range through the standard reprocessing procedure."),

    ("Records stuck in pending validation for 24+ hours",
     "Roughly 40 records have been stuck in a pending-validation state for more than 24 hours and need to be retriggered.",
     "Batch Reprocessing", "P2", "Data Platform Support",
     "2024-09-15T08:00:00Z", "2024-09-15T10:20:00Z", "monitoring-bot", "S. Iyer",
     "A validation job had silently stalled after a transient connection drop to the validation service.",
     "Restarted the validation service, confirmed connectivity, and retriggered the stuck record batch."),

    ("Ad hoc pricing extract requested by Finance",
     "Finance team requests a one-time extract of all pricing records updated in the last quarter for a reconciliation exercise.",
     "Reporting & Extract Request", "P3", "Reporting Services",
     "2024-10-05T14:00:00Z", "2024-10-05T16:00:00Z", "business-portal", "P. Das",
     "Standard ad hoc extract request, no defect.",
     "Built and ran a governed, read-only extract query against the pricing reference tables and delivered the file via the approved secure channel."),

    ("Archive stale test store records in staging",
     "A large number of stale test store records in staging are inflating storage and need to be archived per retention policy.",
     "Data Retention & Archival", "P4", "Data Governance",
     "2024-04-18T09:00:00Z", "2024-04-18T12:00:00Z", "compliance-scan", "A. Banerjee",
     "Test data accumulated over time without a scheduled purge step.",
     "Identified eligible records against the retention policy, archived them, and added a recurring purge job going forward."),

    ("Duplicate store records after upstream resend",
     "Duplicate store reference records appear after the upstream system re-sent a file following a network interruption.",
     "Data Pipeline Failure", "P2", "Data Platform Support",
     "2024-02-11T05:30:00Z", "2024-02-11T08:10:00Z", "monitoring-bot", "R. Sharma",
     "The upstream resubmission was not deduplicated against the original successful send.",
     "Deduplicated the affected records using the natural key and added a resend-detection check to the ingestion job."),

    ("ETL_LoadStoreMaster deadlocks on peak load night",
     "ETL_LoadStoreMaster intermittently fails with a SQL Server deadlock error during peak monthly load nights.",
     "Application Error", "P1", "App Engineering L2",
     "2024-12-01T01:30:00Z", "2024-12-01T06:45:00Z", "job-scheduler", "S. Iyer",
     "Two competing jobs were both writing to the same staging table at overlapping times during peak load.",
     "Adjusted the job schedule to remove the overlap and added a retry-with-backoff step for future contention."),

    ("Bulk region code correction for reorganized franchise group",
     "A franchise group was reassigned to a new region and needs its region code corrected in bulk across all associated stores.",
     "Data Correction Request", "P3", "Data Governance",
     "2025-01-22T10:00:00Z", "2025-01-22T13:20:00Z", "business-portal", "P. Das",
     "Regional reorganization was not reflected in reference data after the business change.",
     "Bulk-updated the region code for the affected store group per the approved business request."),

    ("Retrigger batch after downstream validation rule fix",
     "A batch of records was rejected downstream due to a temporary validation rule mismatch and needs retriggering after the rule was corrected.",
     "Batch Reprocessing", "P2", "Data Platform Support",
     "2025-02-14T09:00:00Z", "2025-02-14T11:40:00Z", "monitoring-bot", "S. Iyer",
     "The downstream validation rule was temporarily out of sync with the upstream data format.",
     "Coordinated with the downstream team to confirm the rule fix, then retriggered the rejected batch."),

    ("Missing Southeast region records after public holiday",
     "Southeast region stores show missing sales records the day after a public holiday.",
     "Data Pipeline Failure", "P2", "Data Platform Support",
     "2025-03-01T06:00:00Z", "2025-03-01T09:30:00Z", "monitoring-bot", "R. Sharma",
     "The upstream POS batch job for that region did not run on the holiday, and the retry was never scheduled.",
     "Manually triggered the missed upstream extract for the holiday date and backfilled the affected records."),

    ("SSIS_LoadStoreMaster times out on large-file day",
     "SSIS_LoadStoreMaster times out on days with an unusually large incoming file, aborting the job.",
     "Application Error", "P2", "App Engineering L2",
     "2025-03-20T03:00:00Z", "2025-03-20T06:15:00Z", "job-scheduler", "A. Banerjee",
     "The default package timeout setting was too low for the largest file-size days seen this year.",
     "Increased the job timeout threshold and added file-size-based alerting ahead of time."),

    ("Recurring monthly product extract for Supply Chain",
     "Supply Chain team requests a recurring monthly extract of updated product reference data.",
     "Reporting & Extract Request", "P3", "Reporting Services",
     "2025-04-01T09:00:00Z", "2025-04-01T10:15:00Z", "business-portal", "P. Das",
     "Standard recurring extract request, no defect.",
     "Scheduled a recurring governed extract job and set up automated secure delivery to the Supply Chain team."),

    ("Purge expired promotional pricing records",
     "Expired promotional pricing records beyond the retention window need to be purged from the active reference tables.",
     "Data Retention & Archival", "P4", "Data Governance",
     "2025-04-15T09:00:00Z", "2025-04-15T11:00:00Z", "compliance-scan", "A. Banerjee",
     "Routine retention-policy purge cycle.",
     "Identified records past the retention window, archived them, and purged them from the active tables per policy."),

    ("No sales data again for a Chicago-region store",
     "A different Chicago-region store again shows a gap in sales records for one business day.",
     "Data Pipeline Failure", "P2", "Data Platform Support",
     "2025-05-06T06:20:00Z", "2025-05-06T09:00:00Z", "monitoring-bot", "R. Sharma",
     "The same upstream leap-year date defect recurring for a different store in the same region, since the upstream fix had not yet been permanently deployed.",
     "Applied the known leap-year patch script and escalated to the upstream team to deploy a permanent fix instead of a recurring manual patch."),

    ("ETL_LoadVendorRef fails after vendor platform migration",
     "ETL_LoadVendorRef fails after the upstream vendor system migrates to a new platform with a slightly different file layout.",
     "Application Error", "P2", "App Engineering L2",
     "2025-06-10T05:00:00Z", "2025-06-10T08:30:00Z", "job-scheduler", "S. Iyer",
     "The vendor migration changed the file layout without advance notice to the support team.",
     "Updated the source mapping to match the new file layout and requested advance notice for future vendor migrations."),

    ("Retrigger batch after code fix deployed",
     "A batch of records that failed due to a since-fixed mapping bug need to be retriggered now that the fix is deployed.",
     "Batch Reprocessing", "P2", "App Engineering L2",
     "2025-06-12T09:00:00Z", "2025-06-12T10:30:00Z", "job-scheduler", "S. Iyer",
     "Records failed during the window before the code fix for the mapping defect was deployed.",
     "Confirmed the fix was live, then retriggered the affected batch through the standard reprocessing procedure."),

    ("Incorrect currency code for new-market stores",
     "A newly onboarded set of international stores has an incorrect currency code in the reference data.",
     "Data Correction Request", "P3", "Data Governance",
     "2025-06-25T11:00:00Z", "2025-06-25T13:10:00Z", "business-portal", "P. Das",
     "The currency code defaulted incorrectly during initial onboarding for the new market.",
     "Bulk-corrected the currency code for the affected store set and verified downstream propagation."),

    ("Three vendor jobs fail the same morning",
     "ETL_LoadVendorRef, ETL_LoadVendorPricing, and ETL_LoadVendorContacts all fail within the same hour after an upstream vendor platform update.",
     "Application Error", "P1", "App Engineering L2",
     "2025-07-02T04:10:00Z", "2025-07-02T08:50:00Z", "job-scheduler", "S. Iyer",
     "The vendor's platform update renamed a shared identifier column referenced by all three packages.",
     "Traced all three failures to the single renamed column, fixed the mapping once, and applied it across all three packages together."),
]

MDM_CLOSED = [
    ("Incorrect address on customer record CUST-55432",
     "Customer CUST-55432 has an incorrect mailing address, causing returned mail. The address needs to be validated and corrected against the source system.",
     "Data Quality Issue", "P3", "Data Governance",
     "2025-07-15T14:00:00Z", "2025-07-15T16:30:00Z", "business-portal", "P. Das",
     "The address was manually entered incorrectly during a data migration and was not caught by validation rules.",
     "Corrected the address for CUST-55432 based on the verified source system data. Added a new validation rule to check for similar address format errors in the future."),

    ("New product SKU-98765 not available in POS systems",
     "The new product SKU-98765, which was approved and mastered yesterday, is not appearing in the point-of-sale (POS) systems for stores in the West region.",
     "Data Provisioning Delay", "P2", "Data Platform Support",
     "2025-08-01T09:10:00Z", "2025-08-01T11:00:00Z", "monitoring-bot", "S. Iyer",
     "The syndication job that provisions new product data to the regional POS systems failed to pick up the new record due to a timing issue with the approval workflow.",
     "Manually triggered the syndication job for SKU-98765. Adjusted the job's dependency to wait for the final approval status before running."),

    ("MDM_Nightly_Customer_Merge job failed with null pointer",
     "The nightly customer master match-and-merge job (MDM_Nightly_Customer_Merge) failed with a null pointer exception, preventing new customer records from being consolidated.",
     "Application Error", "P1", "App Engineering L2",
     "2025-08-03T02:00:00Z", "2025-08-03T05:45:00Z", "job-scheduler", "A. Banerjee",
     "A source system sent a customer record with a null value in a mandatory 'date_of_birth' field, which the merge rule was not designed to handle.",
     "Patched the merge rule to handle null values in the date_of_birth field gracefully. Manually corrected the offending source record and reran the merge job successfully."),

    ("Duplicate supplier records created after manual entry",
     "Two records for the same supplier 'Global Provisions Inc' were created by different teams, causing duplicate entries in the master data.",
     "Data Quality Issue", "P2", "Data Governance",
     "2025-08-05T11:20:00Z", "2025-08-05T14:00:00Z", "business-portal", "P. Das",
     "The standard duplicate-check process was bypassed during a manual override by a user with elevated permissions.",
     "Merged the two supplier records, retaining the golden record and updating all child systems. A review of manual override permissions has been initiated."),

    ("Delay in new employee data provisioning to HR system",
     "Data for a batch of new hires is not appearing in the downstream HR system within the 24-hour SLA.",
     "Data Provisioning Delay", "P2", "Data Platform Support",
     "2025-08-10T09:00:00Z", "2025-08-10T12:30:00Z", "monitoring-bot", "S. Iyer",
     "The provisioning workflow was waiting for a 'manager_id' field that was not yet populated for the new hire batch, causing the process to stall.",
     "Updated the workflow to proceed without the 'manager_id' and flag it for later enrichment. Retriggered the provisioning for the affected employee batch."),
]

MORE_MDM_CLOSED = [
    ("User unable to access Supplier Portal",
     "User 'j.doe' from supplier 'Global Provisions Inc' reports they are receiving an authentication error when trying to log in to the supplier portal.",
     "Access & Permissions", "P3", "App Engineering L2",
     "2025-08-12T15:00:00Z", "2025-08-12T16:00:00Z", "business-portal", "A. Banerjee",
     "The user's account was locked due to multiple failed login attempts. The automated unlock process failed to trigger.",
     "Manually unlocked the user's account and reset their password. Investigating why the automated unlock process failed."),

    ("New user provisioning delayed for 's.jones'",
     "New user 's.jones' was requested 48 hours ago but the account has not been created in the target systems. The SLA is 24 hours.",
     "User Provisioning", "P3", "Data Platform Support",
     "2025-08-14T10:00:00Z", "2025-08-14T11:30:00Z", "business-portal", "S. Iyer",
     "The provisioning workflow was stuck waiting for an approval from a manager who is currently on leave.",
     "Manually escalated the approval to the next level manager. The workflow has been updated to include delegation rules for out-of-office approvals."),

    ("Incorrect holiday hours on portal for store 3456",
     "The public-facing store locator portal is showing standard operating hours for store 3456 for the upcoming public holiday, but it should show reduced hours.",
     "Data Correction Request", "P2", "Data Governance",
     "2025-08-18T13:00:00Z", "2025-08-18T14:00:00Z", "business-portal", "P. Das",
     "A bulk update for holiday hours missed this specific store due to an incorrect region code in the update script's filter.",
     "Manually corrected the holiday hours for store 3456. The bulk update script's filter has been corrected for future runs."),

    ("Employee discount not applying for new hires",
     "A group of new hires from the latest onboarding batch report that their employee discount is not being applied at the point-of-sale.",
     "Data Provisioning Delay", "P2", "Data Platform Support",
     "2025-08-20T09:30:00Z", "2025-08-20T11:00:00Z", "business-portal", "S. Iyer",
     "The job that syncs new employee IDs to the discount eligibility system had not completed its cycle for the new hire batch.",
     "Manually triggered the employee sync job and confirmed the new hires were added to the discount system. The job schedule has been adjusted to run more frequently after large onboarding events."),

    ("Portal search returns 'Invalid Character' error",
     "When searching for products with special characters (e.g., '&', '#') in the name on the internal portal, an 'Invalid Character' error is returned.",
     "Application Error", "P3", "App Engineering L2",
     "2025-08-22T16:00:00Z", "2025-08-22T18:30:00Z", "business-portal", "A. Banerjee",
     "The portal's search input was not properly sanitizing special characters before passing them to the backend API.",
     "Deployed a hotfix to the frontend to properly encode special characters in search queries before sending them to the API."),
]

CLOSED.extend(MDM_CLOSED)
CLOSED.extend(MORE_MDM_CLOSED)

# Today's active queue — deliberately includes:
#  - one strong near-duplicate of a known historical pattern (leap-year bug) -> a strong "wow" match
#  - three incidents that share a root cause (vendor platform update) -> Pattern Spotter demo
#  - one routine, easily-matched retrigger
#  - one genuinely novel issue with no good precedent -> demonstrates the "no match" guardrail honestly
ACTIVE = [
    ("No sales data for store 1189 (Chicago region)",
     "Store 1189 in the Chicago region is showing no sales data for yesterday's business day. Business is asking for an ETA.",
     "Data Pipeline Failure", "P2", "Data Platform Support", "monitoring-bot"),

    ("ETL_LoadVendorPricing failing since this morning",
     "ETL_LoadVendorPricing has failed twice this morning with a column-not-found error. No changes were made on our side recently.",
     "Application Error", "P1", "App Engineering L2", "job-scheduler"),

    ("ETL_LoadVendorContacts failing since this morning",
     "ETL_LoadVendorContacts is failing with a similar error to ETL_LoadVendorPricing, also starting this morning.",
     "Application Error", "P2", "App Engineering L2", "job-scheduler"),

    ("ETL_LoadVendorCatalog also failing today",
     "ETL_LoadVendorCatalog started failing today as well, same general timeframe as the other vendor-related job failures.",
     "Application Error", "P2", "App Engineering L2", "job-scheduler"),

    ("Retrigger ~80 records after BatchTag correction",
     "A batch of about 80 records failed on BatchTag mismatch after a manual upstream correction and needs to be retriggered.",
     "Batch Reprocessing", "P2", "Data Platform Support", "monitoring-bot"),

    ("Dashboard shows inconsistent store counts by region",
     "A regional VP reports the store-count totals on the executive dashboard don't match between two report views, first noticed this morning.",
     "Application Error", "P2", "Reporting Services", "business-portal"),
]


def build():
    incidents = []
    n = 10000
    for (short_desc, desc, category, priority, group, opened, resolved, opened_by, resolved_by,
         root_cause, close_notes) in CLOSED:
        n += 1
        incidents.append({
            "sys_id": f"sys{n:08d}",
            "number": f"INC{n:07d}",
            "short_description": short_desc,
            "description": desc,
            "category": category,
            "priority": priority,
            "state": "Closed",
            "assignment_group": group,
            "opened_at": opened,
            "resolved_at": resolved,
            "sla_due": resolved,
            "opened_by": opened_by,
            "resolved_by": resolved_by,
            "root_cause": root_cause,
            "close_notes": close_notes,
        })

    for (short_desc, desc, category, priority, group, opened_by) in ACTIVE:
        n += 1
        incidents.append({
            "sys_id": f"sys{n:08d}",
            "number": f"INC{n:07d}",
            "short_description": short_desc,
            "description": desc,
            "category": category,
            "priority": priority,
            "state": "New",
            "assignment_group": group,
            "opened_at": "2026-07-24T07:30:00Z",
            "resolved_at": None,
            "sla_due": "2026-07-24T15:30:00Z" if priority == "P1" else "2026-07-25T07:30:00Z",
            "opened_by": opened_by,
            "resolved_by": None,
            "root_cause": None,
            "close_notes": None,
        })

    return incidents


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "incidents.json")
    with open(out_path, "w") as f:
        json.dump(build(), f, indent=2)
    print(f"Wrote {len(build())} incidents to {out_path}")
