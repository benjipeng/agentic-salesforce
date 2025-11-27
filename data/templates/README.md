# Data Templates (CSV headers only)

These files define the columns expected for Bulk API 2.0/REST loads. No data is included yet.

## Files
- `accounts.csv`, `contacts.csv`, `opportunities.csv`, `opportunity_stage_history.csv`
- `cases.csv`, `tasks.csv`
- `products.csv`, `pricebooks.csv`, `pricebook_entries.csv`, `quotes.csv`, `quote_line_items.csv`
- `knowledge.csv` (insert-only), `content_notes.csv`, `feed_items.csv`, `email_messages.csv`

## Load order (recommended)
1) Accounts  
2) Contacts  
3) Opportunities  
4) Products  
5) Pricebooks  
6) PricebookEntries  
7) Quotes  
8) QuoteLineItems  
9) Cases  
10) Tasks  
11) Knowledge (insert only; uses UrlName/ArticleNumber)  
12) ContentNotes  
13) FeedItems  
14) EmailMessage (via REST/Composite)  
15) Files (ContentVersion) upload via REST multipart, then ContentDocumentLink (not templated here)

## Notes
- External IDs: all `*_ExtId__c` columns assume matching External ID fields exist in metadata. Bulk upsert requires `externalIdFieldName`.
- Tasks `WhatExtId_Type` allowed: Account, Opportunity, Case, Quote.
- Knowledge: supports insert; upsert not supported with external IDs. Data Category assignments must be insert/delete.
- EmailMessage and ContentVersion typically require REST, not Bulk 2.0.
- Delete operations require `Id` (Bulk 2.0 ignores externalIdFieldName for delete).
