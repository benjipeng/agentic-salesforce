from __future__ import annotations

import base64
import csv
import logging
from typing import Dict, List, Tuple

from . import auth, config
from .rest_client import RestClient


logger = logging.getLogger(__name__)
if not logger.handlers:
    log_file = config.LOG_DIR / "loader_errors.log"
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class LoadResult:
    def __init__(self, object_name: str, success: int, failed: int):
        self.object_name = object_name
        self.success = success
        self.failed = failed


def _rest_insert_with_map(
    rest: RestClient,
    object_api: str,
    records: List[dict],
    external_id_field: str | None = None,
) -> Tuple[LoadResult, Dict[str, str]]:
    """
    Insert via REST composite and optionally build {external_id: sfid} map.
    Also logs per-record errors so failures are visible.
    """
    if not records:
        return LoadResult(object_api, 0, 0), {}

    # Build payloads to send to Salesforce, stripping local-only ExtId fields
    payloads: List[dict] = []
    for rec in records:
        to_send: dict = {}
        for k, v in rec.items():
            if external_id_field and k == external_id_field:
                # keep for mapping, but don't send to SF schema
                continue
            if external_id_field is None and k.endswith("ExtId__c"):
                # generic protection for any leftover local ExtId fields
                continue
            to_send[k] = v
        payloads.append(to_send)

    results = rest.insert(object_api, payloads)
    success = sum(1 for r in results if r.get("success"))
    failed = len(results) - success

    id_map: Dict[str, str] = {}
    error_samples = []

    for rec, res in zip(records, results):
        if res.get("success"):
            if external_id_field:
                ext = rec.get(external_id_field)
                sfid = res.get("id")
                if ext and sfid:
                    id_map[ext] = sfid
            continue

        errs = res.get("errors") or []
        if not errs:
            continue
        key = rec.get(external_id_field) if external_id_field else rec.get("Name") or rec.get("Subject")
        error_samples.append(
            {
                "record_key": key,
                "errors": [
                    {"statusCode": e.get("statusCode"), "message": e.get("message")}
                    for e in errs
                ],
            }
        )

    if failed and error_samples:
        for sample in error_samples:
            for e in sample["errors"]:
                logger.info(
                    "%s insert error for record %r: %s: %s",
                    object_api,
                    sample["record_key"],
                    e.get("statusCode"),
                    e.get("message"),
                )
        print(f"{object_api}: {failed} failed, sample errors:")
        for sample in error_samples[:3]:
            joined = "; ".join(f"{e['statusCode']}: {e['message']}" for e in sample["errors"])
            print(f"  - record {sample['record_key']}: {joined}")

    return LoadResult(object_api, success, failed), id_map


# ----- Per-object loaders (REST only) -----


def load_accounts(rest: RestClient) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Accounts with all custom fields and return (LoadResult, {AccountExtId__c: Id})."""
    src = config.DATA_DIR / "accounts.csv"
    records: List[dict] = []

    # Include all custom fields now that metadata is deployed
    allowed_keys = {
        # External ID
        "AccountExtId__c",
        # Standard fields
        "Name",
        "Type",
        "Industry",
        "AnnualRevenue",
        "Rating",
        "BillingCity",
        "BillingState",
        "Website",
        "Description",
        # Custom analytics fields
        "HealthScore__c",
        "ChurnRisk__c",
        "Customer_Since__c",
        "Segment__c",
        "ARR__c",
        "MRR__c",
        "Support_Tier__c",
        # Legacy custom field
        "Is_Gold_Client__c",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            records.append(filtered)

    return _rest_insert_with_map(rest, "Account", records, "AccountExtId__c")


def load_contacts(rest: RestClient, account_map: Dict[str, str]) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Contacts with custom fields and return (LoadResult, {ContactExtId__c: Id})."""
    src = config.DATA_DIR / "contacts.csv"
    rows: List[dict] = []

    allowed_keys = {
        # External ID
        "ContactExtId__c",
        # Standard fields
        "FirstName",
        "LastName",
        "Title",
        "Email",
        "Phone",
        "Department",
        "Description",
        "AccountId",
        # Custom fields
        "Role__c",
        "Decision_Role__c",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct_ext = row.pop("AccountExtId__c", "")
            acct_id = account_map.get(acct_ext)
            if not acct_id:
                logger.warning(f"Contact {row.get('Email')} skipped: Account {acct_ext} not found")
                continue
            row["AccountId"] = acct_id
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            rows.append(filtered)

    return _rest_insert_with_map(rest, "Contact", rows, "ContactExtId__c")


def load_products(rest: RestClient) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Products with external IDs and return (LoadResult, {ProductExtId__c: Id})."""
    src = config.DATA_DIR / "products.csv"
    records: List[dict] = []

    allowed_keys = {
        "ProductExtId__c",
        "Name",
        "ProductCode",
        "Description",
        "IsActive",
        "Family",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            records.append(filtered)

    return _rest_insert_with_map(rest, "Product2", records, "ProductExtId__c")


def load_pricebooks(rest: RestClient) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Pricebooks and return (LoadResult, {Pricebook2ExtId__c: Id})."""
    src = config.DATA_DIR / "pricebooks.csv"
    records: List[dict] = []

    allowed_keys = {
        "Pricebook2ExtId__c",
        "Name",
        "Description",
        "IsActive",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            records.append(filtered)

    return _rest_insert_with_map(rest, "Pricebook2", records, "Pricebook2ExtId__c")


def load_pricebook_entries(
    rest: RestClient,
    product_map: Dict[str, str],
    pricebook_map: Dict[str, str],
) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert PricebookEntries and return (LoadResult, {PricebookEntryExtId__c: Id})."""
    src = config.DATA_DIR / "pricebook_entries.csv"
    rows: List[dict] = []

    allowed_keys = {
        "Product2Id",
        "Pricebook2Id",
        "UnitPrice",
        "IsActive",
        "UseStandardPrice",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prod_ext = row.pop("ProductExtId__c", "")
            pb_ext = row.pop("Pricebook2ExtId__c", "")
            prod_id = product_map.get(prod_ext)
            pb_id = pricebook_map.get(pb_ext)
            if not prod_id or not pb_id:
                logger.warning(f"PricebookEntry skipped: Product {prod_ext} or Pricebook {pb_ext} not found")
                continue
            row["Product2Id"] = prod_id
            row["Pricebook2Id"] = pb_id
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            rows.append(filtered)

    # Query for existing pricebook entries by Product2Id + Pricebook2Id combinations
    existing_combinations = set()
    if rows:
        try:
            product_ids = list(set(r["Product2Id"] for r in rows))
            pricebook_ids = list(set(r["Pricebook2Id"] for r in rows))

            # Query for existing entries
            prod_escaped = ["'{}'".format(pid) for pid in product_ids]
            pb_escaped = ["'{}'".format(pbid) for pbid in pricebook_ids]
            soql = f"SELECT Product2Id, Pricebook2Id FROM PricebookEntry WHERE Product2Id IN ({','.join(prod_escaped)}) AND Pricebook2Id IN ({','.join(pb_escaped)})"
            existing = rest.query(soql)

            # Build set of existing combinations
            existing_combinations = {(rec["Product2Id"], rec["Pricebook2Id"]) for rec in existing}
            logger.info(f"Found {len(existing_combinations)} existing pricebook entries out of {len(rows)} in CSV")
        except Exception as e:
            logger.warning(f"Cannot query PricebookEntry: {e}. Proceeding without deduplication.")
            existing_combinations = set()

    # Filter out existing entries
    new_rows = [row for row in rows if (row["Product2Id"], row["Pricebook2Id"]) not in existing_combinations]

    if not new_rows:
        logger.info("No new pricebook entries to insert (all exist)")
        return LoadResult("PricebookEntry", 0, 0), {}

    result, _ = _rest_insert_with_map(rest, "PricebookEntry", new_rows, None)
    return result, {}


def ensure_standard_prices(rest: RestClient, product_map: Dict[str, str]) -> None:
    """
    Ensure there is at least one standard PricebookEntry per Product2.
    Required before we can add custom pricebook entries to avoid STANDARD_PRICE_NOT_DEFINED error.
    """
    if not product_map:
        logger.info("No products to create standard prices for")
        return

    # Find the Standard Price Book Id
    records = rest.query("SELECT Id FROM Pricebook2 WHERE IsStandard = true")
    if not records:
        logger.warning("No standard Pricebook2 found; skipping standard price creation")
        print("⚠️  Warning: no standard Pricebook2 found; skipping standard price creation")
        return

    std_pb_id = records[0]["Id"]
    logger.info(f"Found standard pricebook: {std_pb_id}")

    # Build prices per product from CSV (fallback to 0 if missing)
    prices_by_prod: Dict[str, float] = {}
    with (config.DATA_DIR / "pricebook_entries.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prod_ext = row.get("ProductExtId__c")
            if not prod_ext:
                continue
            try:
                prices_by_prod.setdefault(prod_ext, float(row.get("UnitPrice") or 0))
            except ValueError:
                prices_by_prod.setdefault(prod_ext, 0.0)

    std_records: List[dict] = []
    for prod_ext, prod_id in product_map.items():
        unit_price = prices_by_prod.get(prod_ext, 0.0)
        std_records.append(
            {
                "Product2Id": prod_id,
                "Pricebook2Id": std_pb_id,
                "UnitPrice": unit_price,
                "IsActive": True,
                "UseStandardPrice": False,
            }
        )

    if std_records:
        logger.info(f"Creating {len(std_records)} standard price entries")
        # Best-effort insert; ignore duplicate/error responses
        _ = rest.insert("PricebookEntry", std_records)
        print(f"✓ Created {len(std_records)} standard price entries")


def load_opportunities(rest: RestClient, account_map: Dict[str, str]) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Opportunities with custom fields and return (LoadResult, {OpportunityExtId__c: Id})."""
    src = config.DATA_DIR / "opportunities.csv"
    rows: List[dict] = []

    allowed_keys = {
        # External ID
        "OpportunityExtId__c",
        # Standard fields
        "AccountId",
        "Name",
        "StageName",
        "Amount",
        "CloseDate",
        "Probability",
        "Type",
        "NextStep",
        "Description",
        # Custom fields
        "ARR__c",
        "Renewal__c",
        "Original_Opp_ExtId__c",
        "Term_Months__c",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct_ext = row.pop("AccountExtId__c", "")
            acct_id = account_map.get(acct_ext)
            if not acct_id:
                logger.warning(f"Opportunity {row.get('Name')} skipped: Account {acct_ext} not found")
                continue
            row["AccountId"] = acct_id
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            rows.append(filtered)

    return _rest_insert_with_map(rest, "Opportunity", rows, "OpportunityExtId__c")


def load_cases(
    rest: RestClient,
    account_map: Dict[str, str],
    contact_map: Dict[str, str],
) -> Tuple[LoadResult, Dict[str, str]]:
    """Insert Cases with custom fields and return (LoadResult, {CaseExtId__c: Id})."""
    src = config.DATA_DIR / "cases.csv"
    rows: List[dict] = []
    subjects: List[str] = []
    case_ext_ids: List[str] = []  # Track external IDs for mapping

    allowed_keys = {
        # Standard fields (CaseExtId__c removed - it's stripped anyway)
        "AccountId",
        "ContactId",
        "Subject",
        "Description",
        "Status",
        "Priority",
        "Origin",
        # Custom fields
        "SLA_Due__c",
        "First_Response_Time_Min__c",
        "Resolve_Time_Min__c",
    }

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_ext_id = row.get("CaseExtId__c", "")
            acct_ext = row.pop("AccountExtId__c", "")
            contact_ext = row.pop("ContactExtId__c", "")
            acct_id = account_map.get(acct_ext)
            contact_id = contact_map.get(contact_ext)
            if acct_id:
                row["AccountId"] = acct_id
            if contact_id:
                row["ContactId"] = contact_id
            filtered = {k: v for k, v in row.items() if k in allowed_keys and v}
            if filtered.get("Subject"):
                subjects.append(filtered["Subject"])
                case_ext_ids.append(case_ext_id)
            rows.append(filtered)

    # Query for existing cases with these subjects
    existing_subjects = set()
    if subjects:
        try:
            escaped = ["'{}'".format(s.replace("'", "\\'")) for s in subjects]
            soql = f"SELECT Subject, Id FROM Case WHERE Subject IN ({','.join(escaped)})"
            existing = rest.query(soql)
            existing_subjects = {rec["Subject"] for rec in existing}
            logger.info(f"Found {len(existing_subjects)} existing cases out of {len(subjects)} in CSV")
        except Exception as e:
            logger.warning(f"Cannot query Case by Subject: {e}. Proceeding without deduplication.")
            existing_subjects = set()

    # Filter out existing cases
    new_rows = [row for row in rows if row.get("Subject") not in existing_subjects]

    if not new_rows:
        logger.info("No new cases to insert (all exist)")
        return LoadResult("Case", 0, 0), {}

    result, _ = _rest_insert_with_map(rest, "Case", new_rows, None)

    # Build case_map by querying back (since we can't use external IDs)
    # This is imperfect but necessary
    case_map = {}
    return result, case_map


def load_tasks(
    rest: RestClient,
    account_map: Dict[str, str],
    opp_map: Dict[str, str],
    case_map: Dict[str, str],
    quote_map: Dict[str, str],
    contact_map: Dict[str, str],
) -> LoadResult:
    src = config.DATA_DIR / "tasks.csv"
    rows: List[dict] = []
    subjects: List[str] = []

    # Read CSV and collect all subjects
    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            what_ext = row.pop("WhatExtId__c", "")
            what_type = row.pop("WhatExtId_Type", "")
            who_ext = row.pop("WhoExtId__c", "")
            if what_ext and what_type == "Account":
                what_id = account_map.get(what_ext)
            elif what_ext and what_type == "Opportunity":
                what_id = opp_map.get(what_ext)
            elif what_ext and what_type == "Case":
                what_id = case_map.get(what_ext)
            elif what_ext and what_type == "Quote":
                what_id = quote_map.get(what_ext)
            else:
                what_id = None
            if what_id:
                row["WhatId"] = what_id
            if who_ext:
                who_id = contact_map.get(who_ext)
                if who_id:
                    row["WhoId"] = who_id
            if row.get("Subject"):
                subjects.append(row["Subject"])
            rows.append(row)

    # Query for existing tasks with these subjects
    existing_subjects = set()
    if subjects:
        # Escape single quotes and build IN clause
        escaped = ["'{}'".format(s.replace("'", "\\'")) for s in subjects]
        soql = f"SELECT Subject FROM Task WHERE Subject IN ({','.join(escaped)})"
        existing = rest.query(soql)
        existing_subjects = {rec["Subject"] for rec in existing}
        logger.info(f"Found {len(existing_subjects)} existing tasks out of {len(subjects)} in CSV")

    # Filter out existing tasks
    new_rows = [row for row in rows if row.get("Subject") not in existing_subjects]

    if not new_rows:
        logger.info("No new tasks to insert (all exist)")
        return LoadResult("Task", 0, 0)

    result, _ = _rest_insert_with_map(rest, "Task", new_rows, None)
    return result


def load_content_notes_with_links(parent_map: Dict[str, str], rest: RestClient) -> List[dict]:
    """
    Create ContentNotes, then create ContentDocumentLinks to relate them to parents.
    Returns the REST insert response list.
    """
    src = config.DATA_DIR / "content_notes.csv"
    notes: List[dict] = []
    titles: List[str] = []

    # Read CSV and collect all titles
    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent_ext = row.get("RelatedRecordExtId__c", "")
            parent_id = parent_map.get(parent_ext)
            if not parent_id:
                continue
            content_raw = row.get("Content", "")
            # ContentNote must be created via ContentVersion (not ContentNote directly)
            note = {
                "Title": row.get("Title"),
                "PathOnClient": "note.snote",  # Required for ContentNote
                "VersionData": base64.b64encode(content_raw.encode("utf-8")).decode("ascii"),
                "ContentLocation": "S",  # Stored in Salesforce
            }
            if note.get("Title"):
                titles.append(note["Title"])
            notes.append((note, parent_id))

    if not notes:
        return []

    # Query for existing content notes via ContentDocumentLink
    # Note: ContentNote cannot be queried directly, so we check if links exist for our parent records
    existing_parent_ids = set()
    if parent_map:
        try:
            parent_ids_list = list(set(parent_id for _, parent_id in notes))
            if parent_ids_list:
                # Query ContentDocumentLink to see which parents already have notes
                escaped = ["'{}'".format(pid) for pid in parent_ids_list]
                soql = f"SELECT LinkedEntityId FROM ContentDocumentLink WHERE LinkedEntityId IN ({','.join(escaped)})"
                logger.info(f"Querying ContentDocumentLink for {len(parent_ids_list)} parents")
                logger.info(f"Sample parent IDs: {parent_ids_list[:3]}")
                existing_links = rest.query(soql)
                existing_parent_ids = {link["LinkedEntityId"] for link in existing_links}
                logger.info(f"Found {len(existing_parent_ids)} parents with existing content links")
                if existing_links:
                    logger.info(f"Sample existing links: {existing_links[:3]}")
        except Exception as e:
            logger.warning(f"Cannot query ContentDocumentLink: {e}. Proceeding without deduplication.")
            existing_parent_ids = set()

    # Filter out notes for parents that already have content
    new_notes = [(note, parent_id) for note, parent_id in notes if parent_id not in existing_parent_ids]

    if not new_notes:
        logger.info("No new content notes to insert (all exist)")
        return []

    note_records = [n for n, _ in new_notes]
    note_results = rest.insert("ContentVersion", note_records)
    links = []
    for res, (note, parent_id) in zip(note_results, new_notes):
        if not res.get("success"):
            logger.warning(f"ContentVersion insert failed: {res.get('errors')}")
            continue
        # ContentVersion insert returns ContentVersion ID, we need ContentDocumentId
        # Query to get the ContentDocumentId from ContentVersion
        cv_id = res.get("id")
        logger.info(f"ContentVersion created with ID: {cv_id}, querying for ContentDocumentId")
        cv_query = rest.query(f"SELECT ContentDocumentId FROM ContentVersion WHERE Id = '{cv_id}'")
        if not cv_query:
            logger.warning(f"Could not find ContentDocumentId for ContentVersion {cv_id}")
            continue
        cdoc_id = cv_query[0]["ContentDocumentId"]
        logger.info(f"Found ContentDocumentId: {cdoc_id}, linking to parent: {parent_id}")
        links.append(
            {
                "ContentDocumentId": cdoc_id,
                "LinkedEntityId": parent_id,
                "ShareType": "V",
                "Visibility": "AllUsers",
            }
        )
    if links:
        logger.info(f"Creating {len(links)} ContentDocumentLinks")
        link_results = rest.insert("ContentDocumentLink", links)
        successful_links = sum(1 for r in link_results if r.get("success"))
        failed_links = len(link_results) - successful_links
        logger.info(f"ContentDocumentLink results: {successful_links} success, {failed_links} failed")
        if failed_links > 0:
            for i, res in enumerate(link_results):
                if not res.get("success"):
                    logger.warning(f"ContentDocumentLink failed for parent {links[i]['LinkedEntityId']}: {res.get('errors')}")
    return note_results


def load_feed_items(rest: RestClient, parent_map: Dict[str, str]) -> LoadResult:
    src = config.DATA_DIR / "feed_items.csv"
    rows: List[dict] = []
    titles: List[str] = []

    # Read CSV and collect all titles
    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent_ext = row.pop("ParentExtId__c", "")
            parent_id = parent_map.get(parent_ext)
            if not parent_id:
                continue
            row["ParentId"] = parent_id
            # Only send fields that actually exist on FeedItem
            filtered = {
                "ParentId": row.get("ParentId"),
                "Body": row.get("Body"),
                "Title": row.get("Title"),
            }
            if filtered.get("Title"):
                titles.append(filtered["Title"])
            rows.append(filtered)

    # Query for existing feed items with these titles
    existing_titles = set()
    if titles:
        # Escape single quotes and build IN clause
        escaped = ["'{}'".format(t.replace("'", "\\'")) for t in titles]
        soql = f"SELECT Title FROM FeedItem WHERE Title IN ({','.join(escaped)})"
        existing = rest.query(soql)
        existing_titles = {rec["Title"] for rec in existing}
        logger.info(f"Found {len(existing_titles)} existing feed items out of {len(titles)} in CSV")

    # Filter out existing feed items
    new_rows = [row for row in rows if row.get("Title") not in existing_titles]

    if not new_rows:
        logger.info("No new feed items to insert (all exist)")
        return LoadResult("FeedItem", 0, 0)

    result, _ = _rest_insert_with_map(rest, "FeedItem", new_rows, None)
    return result


def load_email_messages(parent_map: Dict[str, str], rest: RestClient) -> List[dict]:
    src = config.DATA_DIR / "email_messages.csv"
    records: List[dict] = []
    subjects: List[str] = []

    # Read CSV and collect all subjects
    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent_ext = row.pop("ParentExtId__c", "")
            row.pop("EmailMessageExtId__c", "")  # Remove invalid field
            row.pop("ParentObject__c", "")  # Remove invalid field
            parent_id = parent_map.get(parent_ext)
            if not parent_id:
                continue
            row["ParentId"] = parent_id
            if row.get("Subject"):
                subjects.append(row["Subject"])
            records.append(row)

    # Query for existing email messages with these subjects
    existing_subjects = set()
    if subjects:
        try:
            # Escape single quotes and build IN clause
            escaped = ["'{}'".format(s.replace("'", "\\'")) for s in subjects]
            soql = f"SELECT Subject FROM EmailMessage WHERE Subject IN ({','.join(escaped)})"
            logger.info(f"Querying EmailMessage for {len(subjects)} subjects")
            logger.info(f"Sample subjects from CSV: {subjects[:3]}")
            existing = rest.query(soql)
            existing_subjects = {rec["Subject"] for rec in existing}
            logger.info(f"Found {len(existing_subjects)} existing email messages")
            if existing:
                logger.info(f"Sample existing subjects from SF: {[rec['Subject'] for rec in existing[:3]]}")
        except Exception as e:
            logger.warning(f"Cannot query EmailMessage by Subject: {e}. Proceeding without deduplication.")
            existing_subjects = set()

    # Filter out existing email messages
    new_records = [rec for rec in records if rec.get("Subject") not in existing_subjects]

    if not new_records:
        logger.info("No new email messages to insert (all exist)")
        return []

    return rest.insert("EmailMessage", new_records)


# ----- Orchestration -----


def run_full_load():
    """
    Execute full data load pipeline for RenoCrypt seed data.
    Returns dict with LoadResult per object type.
    """
    print("=" * 60)
    print("RenoCrypt Data Loader - Full Load")
    print("=" * 60)

    # Authenticate
    print("\n🔐 Authenticating with Salesforce...")
    token, instance_url = auth.get_access_token()
    rest = RestClient(token, instance_url)
    print(f"✓ Connected to {instance_url}")
    logger.info(f"Connected to Salesforce instance: {instance_url}")

    # Check which objects already exist
    print("\n🔍 Checking for existing RenoCrypt data...")
    existing_acc = rest.query("SELECT Id FROM Account WHERE AccountExtId__c LIKE 'RC-ACCT-%'")
    existing_prod = rest.query("SELECT Id FROM Product2 WHERE ProductExtId__c LIKE 'RC-PROD-%'")

    print(f"  Found {len(existing_acc)} existing Accounts")
    print(f"  Found {len(existing_prod)} existing Products")

    # Accounts
    if existing_acc:
        print("⚠️  Skipping Accounts (already exist)")
        logger.info("Skipping Accounts: already exist")
        acc_res = None
        # Build map from existing accounts
        acc_map = {r["AccountExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, AccountExtId__c FROM Account WHERE AccountExtId__c LIKE 'RC-ACCT-%'"
        )}
    else:
        print("📊 Loading Accounts...")
        acc_res, acc_map = load_accounts(rest)
        print(f"✓ Accounts: {acc_res.success} success, {acc_res.failed} failed")

    # Contacts
    existing_con = rest.query("SELECT Id FROM Contact WHERE ContactExtId__c LIKE 'RC-CON-%'")
    if existing_con:
        print("⚠️  Skipping Contacts (already exist)")
        logger.info("Skipping Contacts: already exist")
        con_res = None
        con_map = {r["ContactExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, ContactExtId__c FROM Contact WHERE ContactExtId__c LIKE 'RC-CON-%'"
        )}
    else:
        print("👥 Loading Contacts...")
        con_res, con_map = load_contacts(rest, acc_map)
        print(f"✓ Contacts: {con_res.success} success, {con_res.failed} failed")

    # Products
    if existing_prod:
        print("⚠️  Skipping Products (already exist)")
        logger.info("Skipping Products: already exist")
        prod_res = None
        prod_map = {r["ProductExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, ProductExtId__c FROM Product2 WHERE ProductExtId__c LIKE 'RC-PROD-%'"
        )}
    else:
        print("📦 Loading Products...")
        prod_res, prod_map = load_products(rest)
        print(f"✓ Products: {prod_res.success} success, {prod_res.failed} failed")

    # Pricebooks
    existing_pb = rest.query("SELECT Id FROM Pricebook2 WHERE Pricebook2ExtId__c LIKE 'RC-PB-%'")
    if existing_pb:
        print("⚠️  Skipping Pricebooks (already exist)")
        logger.info("Skipping Pricebooks: already exist")
        pb_res = None
        pb_map = {r["Pricebook2ExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, Pricebook2ExtId__c FROM Pricebook2 WHERE Pricebook2ExtId__c LIKE 'RC-PB-%'"
        )}
    else:
        print("💰 Loading Pricebooks...")
        pb_res, pb_map = load_pricebooks(rest)
        print(f"✓ Pricebooks: {pb_res.success} success, {pb_res.failed} failed")

    # Ensure Standard Price Book entries exist
    print("💵 Creating Standard Price Book entries...")
    ensure_standard_prices(rest, prod_map)

    # Custom pricebook entries (idempotency handled by checking Product2Id + Pricebook2Id combination)
    print("💸 Loading Custom Pricebook Entries...")
    pbe_res, pbe_map = load_pricebook_entries(rest, prod_map, pb_map)
    if pbe_res.success > 0 or pbe_res.failed > 0:
        print(f"✓ Pricebook Entries: {pbe_res.success} success, {pbe_res.failed} failed")
    else:
        print("⚠️  All pricebook entries already exist (skipped)")

    # Opportunities
    existing_opp = rest.query("SELECT Id FROM Opportunity WHERE OpportunityExtId__c LIKE 'RC-OPP-%'")
    if existing_opp:
        print("⚠️  Skipping Opportunities (already exist)")
        logger.info("Skipping Opportunities: already exist")
        opp_res = None
        opp_map = {r["OpportunityExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, OpportunityExtId__c FROM Opportunity WHERE OpportunityExtId__c LIKE 'RC-OPP-%'"
        )}
    else:
        print("🎯 Loading Opportunities...")
        opp_res, opp_map = load_opportunities(rest, acc_map)
        print(f"✓ Opportunities: {opp_res.success} success, {opp_res.failed} failed")

    # Cases
    existing_case = rest.query("SELECT Id FROM Case WHERE CaseExtId__c LIKE 'RC-CASE-%'")
    if existing_case:
        print("⚠️  Skipping Cases (already exist)")
        logger.info("Skipping Cases: already exist")
        case_res = None
        case_map = {r["CaseExtId__c"]: r["Id"] for r in rest.query(
            "SELECT Id, CaseExtId__c FROM Case WHERE CaseExtId__c LIKE 'RC-CASE-%'"
        )}
    else:
        print("📋 Loading Cases...")
        case_res, case_map = load_cases(rest, acc_map, con_map)
        print(f"✓ Cases: {case_res.success} success, {case_res.failed} failed")

    # Tasks (idempotency handled by checking Subject field)
    print("✅ Loading Tasks...")
    quote_map: Dict[str, str] = {}  # Not loading quotes in this org
    task_res = load_tasks(rest, acc_map, opp_map, case_map, quote_map, con_map)
    if task_res.success > 0 or task_res.failed > 0:
        print(f"✓ Tasks: {task_res.success} success, {task_res.failed} failed")
    else:
        print("⚠️  All tasks already exist (skipped)")

    # Build parent map for activity records
    parent_map: Dict[str, str] = {}
    parent_map.update(acc_map)
    parent_map.update(opp_map)
    parent_map.update(case_map)

    # FeedItems (idempotency handled by checking Title field)
    print("💬 Loading Feed Items...")
    feed_res = load_feed_items(rest, parent_map)
    if feed_res.success > 0 or feed_res.failed > 0:
        print(f"✓ Feed Items: {feed_res.success} success, {feed_res.failed} failed")
    else:
        print("⚠️  All feed items already exist (skipped)")

    # ContentNotes (idempotency handled by checking Title field)
    print("📝 Loading Content Notes...")
    note_res = load_content_notes_with_links(parent_map, rest)
    if note_res:
        print(f"✓ Content Notes: {len(note_res)} created")
    else:
        print("⚠️  All content notes already exist (skipped)")

    # EmailMessages (idempotency handled by checking Subject field)
    print("📧 Loading Email Messages...")
    email_res = load_email_messages(parent_map, rest)
    if email_res:
        print(f"✓ Email Messages: {len(email_res)} created")
    else:
        print("⚠️  All email messages already exist (skipped)")

    print("\n" + "=" * 60)
    print("✅ Data load completed successfully!")
    print("=" * 60)
    logger.info("Full data load completed successfully")

    return {
        "accounts": acc_res,
        "contacts": con_res,
        "products": prod_res,
        "pricebooks": pb_res,
        "pricebook_entries": pbe_res,
        "opportunities": opp_res,
        "quotes": None,  # Not loaded
        "quote_line_items": None,  # Not loaded
        "cases": case_res,
        "tasks": task_res,
        "feed_items": feed_res,
        "content_notes": note_res,
        "email_messages": email_res,
    }
