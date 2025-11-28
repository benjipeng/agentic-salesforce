# Scratch Data Loader Behavior and Salesforce Quirks

This document explains **why the original Bulk API + custom‑field approach failed** in this scratch org, and **what the current REST‑based loader is doing instead**. It's meant as a technical reference for future debugging and for designing more robust loaders.

## 1. Initial Design (Bulk 2.0 + External IDs)

Original plan:

- Use **Bulk API 2.0** (`/services/data/vXX.X/jobs/ingest`) from Python.
- For each core object (Account, Contact, Product2, Pricebook2, PricebookEntry, Opportunity, Case, Task, etc.):
  - Perform **upserts** using custom external ID fields such as `AccountExtId__c`, `ProductExtId__c`, `Pricebook2ExtId__c`, `CaseExtId__c`, `TaskExtId__c`.
  - Parse Bulk **successfulResults** CSVs to build `{ExternalId → Id}` maps.
- Push a rich schema in one shot, including many custom analytics fields:
  - Accounts: `HealthScore__c`, `ChurnRisk__c`, `Customer_Since__c`, `Segment__c`, `ARR__c`, `MRR__c`, `Support_Tier__c`, etc.
  - Cases: `SLA_Due__c`, `First_Response_Time_Min__c`, `Resolve_Time_Min__c`.
  - Opportunities: `ARR__c`, `Renewal__c`, `Original_Opp_ExtId__c`, `Term_Months__c`.
  - Various `*_ExtId__c` fields on many objects.

This approach is valid **if and only if** the org has:

- Those custom fields actually **deployed** in metadata.
- External ID custom fields marked with `<externalId>true</externalId>`.
- Appropriate **field‑level security** (FLS) so the API user can see the fields.
- Stable duplicate rules, validation rules, and Standard PriceBook entries already in place.

In this scratch org, those conditions were not fully met.

## 2. Problems Observed With the Original Approach

### 2.1 Bulk upsert external ID mismatch

When we attempted Bulk upsert jobs with `externalIdFieldName` set, Salesforce returned errors such as:

- `InvalidJob : Field name provided, AccountExtId__c does not match an External ID for Account`

Root cause:

- For Bulk upsert, `externalIdFieldName` **must reference a field that is marked as External ID** on that object.
- At the time of the first runs, fields like `AccountExtId__c` were not recognized as External ID by the org (either not deployed yet, or the `<externalId>true</externalId>` bit was not active in that scratch).

Effect:

- Bulk 2.0 job creation failed for upsert, so no rows were processed.

### 2.2 Bulk 2.0 “unprocessed” rows with opaque feedback

After switching to Bulk **insert** to avoid the upsert external ID issue, the jobs still did not insert data:

- `success_*.csv` files contained only headers (no `sf__Id` rows).
- All our CSV rows appeared in `unprocessed_*.csv`.

In Bulk 2.0, **unprocessed** means:

- Salesforce created the job and accepted the CSV file, but **never attempted to insert those records** (often due to job‑level problems, malformed headers, or other pre‑validation issues).
- We had to manually inspect CSV outputs to infer that nothing got inserted; Bulk did not surface clear per‑record errors in the simple HTTP 2xx responses we were logging.

Effect:

- From the outside it looked like the jobs “succeeded”, but the org remained empty.

### 2.3 Missing / invisible custom fields (`INVALID_FIELD`)

Once we moved to REST to debug more directly, we started seeing explicit per‑record errors:

- `INVALID_FIELD: No such column 'AccountExtId__c' on sobject of type Account`
- `INVALID_FIELD: No such column 'ProductExtId__c' on sobject of type Product2`
- `INVALID_FIELD: No such column 'Pricebook2ExtId__c' on sobject of type Pricebook2`
- `INVALID_FIELD: No such column 'CaseExtId__c' on sobject of type Case`
- `INVALID_FIELD: No such column 'TaskExtId__c' on sobject of type Task`
- `INVALID_FIELD: No such column 'HealthScore__c' on sobject of type Account`
- `INVALID_FIELD: No such column 'ChurnRisk__c' on sobject of type Account`
- `INVALID_FIELD: No such column 'SLA_Due__c' on sobject of type Case`
- `INVALID_FIELD: No such column 'First_Response_Time_Min__c' on sobject of type Case`

This occurred **even though** the repo contains metadata files like:

- `force-app/main/default/objects/Account/fields/HealthScore__c.field-meta.xml`
- `force-app/main/default/objects/Case/fields/SLA_Due__c.field-meta.xml`

Possible reasons in a scratch org:

- Metadata was not actually deployed to this scratch before the data load attempts.
- Or metadata was deployed, but the integration user (JWT login) did not have FLS visibility, and Salesforce reports that as “No such column …” for the API.

Effect:

- Any attempt to use these fields in REST/Bulk inserts caused **every row** for that object to fail.

### 2.4 Standard PriceBook constraint (`STANDARD_PRICE_NOT_DEFINED`)

When inserting `PricebookEntry` rows for a custom pricebook, Salesforce responded with:

- `STANDARD_PRICE_NOT_DEFINED: Before creating a custom price, create a standard price.`

Salesforce rule:

- For each `Product2`, there must be **at least one PricebookEntry in the Standard Price Book** before you can create entries in a custom pricebook for that product.

Effect:

- All `PricebookEntry` inserts failed until we seeded Standard PriceBook entries first.

### 2.5 Duplicate rules (`DUPLICATES_DETECTED`)

Once Accounts successfully loaded, repeated runs of the loader produced:

- `DUPLICATES_DETECTED: Duplicate Alert`

Salesforce behavior:

- Duplicate rules can be configured so that inserts which match an existing record on certain criteria (e.g., `Name`, `Website`) are blocked with `DUPLICATES_DETECTED`.

Effect:

- Additional Account insert attempts fail (correctly) and do not add more records. The accounts that were inserted in an earlier run remain, but the load is no longer idempotent.

## 3. Current Strategy (REST Composite + Conservative Fields)

Given the above issues and the relatively small dataset (tens of records per object), we changed approach to something more robust and transparent.

### 3.1 REST composite inserts instead of Bulk

We now use `RestClient.insert` pointing to:

- `/services/data/vXX.X/composite/sobjects`

Behavior:

- Up to 200 records per call.
- For each record, Salesforce returns:
  - `success: true/false`
  - `id` of the record (if success).
  - `errors: [...]` array (if failure), including `statusCode` and `message`.

In `pipeline.py`:

- `_rest_insert_with_map(rest, object_api, records, external_id_field)`:
  - Calls `rest.insert(object_api, payloads)`.
  - Counts `success` and `failed` records.
  - Optionally builds `{external_id_field → id}` maps for successful rows.
  - Logs all per‑record errors to `agents/python/logs/loader_errors.log`.
  - Prints a few sample errors to stdout for quick diagnosis.

This gives immediate, human‑readable feedback on why a record failed (e.g., `INVALID_FIELD`, `STANDARD_PRICE_NOT_DEFINED`, `DUPLICATES_DETECTED`), something Bulk 2.0 made difficult.

### 3.2 Treating `*_ExtId__c` as local keys only

Because custom External ID fields were a source of `INVALID_FIELD` errors, the loader now:

- **Keeps** `*_ExtId__c` columns in the CSVs and in Python objects.
- **Strips** those fields from the JSON payload sent to Salesforce:
  - In `_rest_insert_with_map`, for each record we build a `to_send` dict that:
    - Excludes `external_id_field` (e.g. `AccountExtId__c`) from the outgoing JSON.
    - Excludes any other suffix‑matching `*ExtId__c` when `external_id_field` is `None`.
- Uses the REST `id` from successful results to build maps such as:
  - `{AccountExtId__c → Account.Id}`
  - `{ContactExtId__c → Contact.Id}`
  - `{OpportunityExtId__c → Opportunity.Id}`
  - `{CaseExtId__c → Case.Id}`

These maps are then used to resolve foreign keys:

- Contacts → Accounts (`AccountId` from `AccountExtId__c`).
- Opportunities → Accounts.
- Cases → Accounts/Contacts.
- Tasks → Account/Opportunity/Case (WhatId) and Contact (WhoId).
- FeedItems / ContentNotes / EmailMessages → Account/Opportunity/Case.

This avoids relying on Salesforce recognizing those fields as real External IDs while still giving us stable join keys in our synthetic dataset.

### 3.3 Whitelisting safe fields per object

To avoid repeated `INVALID_FIELD` issues from missing or invisible custom fields, the loader only sends **known‑safe fields** for each object:

- `Account`:
  - Allowed: `Name`, `Type`, `Industry`, `AnnualRevenue`, `Rating`, `BillingCity`, `BillingState`, `Website`, `Is_Gold_Client__c`, `Description`.
  - Not sent (though present in CSV): `HealthScore__c`, `ChurnRisk__c`, `Customer_Since__c`, `Segment__c`, `ARR__c`, `MRR__c`, `Support_Tier__c`.

- `Contact`:
  - Allowed: `FirstName`, `LastName`, `Title`, `Email`, `Phone`, `Department`, `Description`, `AccountId`.
  - Not sent: `Role__c`, `Decision_Role__c`.

- `Opportunity`:
  - Allowed: `Name`, `StageName`, `Amount`, `CloseDate`, `Probability`, `Type`, `NextStep`, `Description`, `AccountId`.
  - Not sent: `ARR__c`, `Renewal__c`, `Original_Opp_ExtId__c`, `Term_Months__c`.

- `Case`:
  - Allowed: `Subject`, `Description`, `Status`, `Priority`, `Origin`, `AccountId`, `ContactId`.
  - Not sent: `SLA_Due__c`, `First_Response_Time_Min__c`, `Resolve_Time_Min__c`.

- `Task`:
  - Allowed: `Subject`, `Description`, `Status`, `Priority`, `ActivityDate`, `WhatId`, `WhoId`.
  - `TaskExtId__c` is used only in CSV and not sent.

- `FeedItem`:
  - Allowed: `ParentId`, `Body`, `Title`.
  - Not sent: `FeedItemExtId__c`, `ParentExtId__c`, `ParentObject__c`, `CreatedDate`.

- `ContentNote` / `ContentDocumentLink`:
  - Inserts only real fields required for ContentNotes and links (binary `Content`, `Title`, `ContentDocumentId`, `LinkedEntityId`, etc.).

- `EmailMessage`:
  - Sends only valid `EmailMessage` fields present in CSV and supported by the org, plus `ParentId` resolved from ext IDs.

This conservative whitelisting ensures we get a working dataset now, even if not all planned custom fields are live in the org.

### 3.4 Handling Standard Price Book

Before inserting custom `PricebookEntry` records, the loader now:

- Queries for `Pricebook2` where `IsStandard = true` to obtain the Standard Price Book Id.
- Builds one Standard `PricebookEntry` per Product2 with a simple unit price (taken from our `pricebook_entries.csv` as a fallback).
- Inserts these Standard entries (ignoring duplicate errors).

Only after that does it insert custom `PricebookEntry` rows for the RenoCrypt pricebook.

This avoids the `STANDARD_PRICE_NOT_DEFINED` error and aligns with Salesforce pricing constraints.

### 3.5 Duplicate behavior and idempotency

Because this scratch org has duplicate rules, re‑running the loader can trigger:

- `DUPLICATES_DETECTED: Duplicate Alert` when trying to insert Accounts that already exist.

Current behavior:

- Accounts that already exist are **not inserted again**; Salesforce blocks them.
- Tasks and some other objects are currently **insert‑only**, so re‑running the loader can create duplicates (e.g., 30 Tasks per run).

For now we handle this by:

- Treating the loader as a **“seed once”** tool for a fresh scratch org.
- If duplicates are created during experimentation, deleting them in bulk and reloading.

In the future, proper idempotency could be achieved by:

- Ensuring `*_ExtId__c` fields truly exist and are flagged as External IDs.
- Switching to REST upsert flows (or Bulk again) keyed on those External IDs.

## 4. Practical Takeaways for This Project

- Bulk API 2.0 is powerful but **not friendly for fast iteration** in a small scratch org with evolving metadata; REST composite with clear per‑record errors is much easier to debug.
- In a scratch org, **metadata in the repo does not guarantee** fields are usable:
  - You must confirm deployment and FLS if you want to use custom fields via API.
- External ID fields are great for idempotent loads, but only when:
  - They are actually present, marked as External ID, and visible.
  - The org’s duplicate rules and validation rules are tuned accordingly.
- Salesforce enforces several object‑specific invariants that loaders must respect:
  - Standard Price Book entries per Product2 before custom pricebooks.
  - Duplicate rules may block inserts without raising HTTP 4xx; instead they appear as per‑record errors (`DUPLICATES_DETECTED`) inside a 200 response body.
- For **small, rich synthetic datasets** like this RenoCrypt CRM seed, a REST‑based loader that:
  - Uses local external IDs purely for mapping, and
  - Whitelists known‑good fields,
  is the most pragmatic and reliable approach.

This document should be kept alongside the loader code under `agents/python/loaders/` so future changes (e.g., enabling more custom fields, turning on true External IDs, or re‑enabling Bulk) can be made with a clear understanding of Salesforce’s behavior in this scratch setup.

