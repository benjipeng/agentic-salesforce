// Seed realistic CRM data for AI agent development
// Run: sf apex run --file scripts/apex/seed-crm-data.apex --target-org MyFirstScratch
// Set CLEANUP_MODE = true to delete existing seed data before inserting

Boolean CLEANUP_MODE = false; // Set to true to clean existing data first

// --- ACCOUNTS ---
List<String> accountNames = new List<String>{
    'Acme Corporation',
    'GlobalTech Industries',
    'Sunrise Healthcare',
    'Summit Financial Group',
    'EduLearn Platform'
};

// Check for existing accounts (idempotency)
Map<String, Account> existingAccounts = new Map<String, Account>();
for (Account a : [SELECT Id, Name FROM Account WHERE Name IN :accountNames]) {
    existingAccounts.put(a.Name, a);
}

List<Account> accounts = new List<Account>();
if (CLEANUP_MODE && !existingAccounts.isEmpty()) {
    delete existingAccounts.values();
    System.debug('✓ Cleaned up ' + existingAccounts.size() + ' existing Accounts');
    existingAccounts.clear();
}

// Create accounts only if they don't exist
for (String name : accountNames) {
    if (!existingAccounts.containsKey(name)) {
        if (name == 'Acme Corporation') {
            accounts.add(new Account(
                Name = name,
                Industry = 'Technology',
                AnnualRevenue = 5000000,
                Rating = 'Hot',
                Phone = '415-555-1234',
                Website = 'https://acme.example.com',
                Description = 'Enterprise software company. Key decision maker is CTO. Currently evaluating our platform for Q1 rollout. Has budget approved.',
                BillingCity = 'San Francisco',
                BillingState = 'CA',
                Is_Gold_Client__c = true
            ));
        } else if (name == 'GlobalTech Industries') {
            accounts.add(new Account(
                Name = name,
                Industry = 'Manufacturing',
                AnnualRevenue = 12000000,
                Rating = 'Warm',
                Phone = '212-555-5678',
                Website = 'https://globaltech.example.com',
                Description = 'Manufacturing conglomerate with 3 subsidiaries. Interested in supply chain optimization. Previous vendor contract ends in March.',
                BillingCity = 'New York',
                BillingState = 'NY',
                Is_Gold_Client__c = true
            ));
        } else if (name == 'Sunrise Healthcare') {
            accounts.add(new Account(
                Name = name,
                Industry = 'Healthcare',
                AnnualRevenue = 8000000,
                Rating = 'Hot',
                Phone = '312-555-9012',
                Description = 'Regional hospital network. HIPAA compliance is critical. Looking for patient engagement solutions. Budget cycle ends in December.',
                BillingCity = 'Chicago',
                BillingState = 'IL',
                Is_Gold_Client__c = false
            ));
        } else if (name == 'Summit Financial Group') {
            accounts.add(new Account(
                Name = name,
                Industry = 'Finance',
                AnnualRevenue = 25000000,
                Rating = 'Cold',
                Phone = '617-555-3456',
                Description = 'Investment firm. Had a bad experience with competitor product. Needs extensive security review before any purchase. Long sales cycle expected.',
                BillingCity = 'Boston',
                BillingState = 'MA',
                Is_Gold_Client__c = false
            ));
        } else if (name == 'EduLearn Platform') {
            accounts.add(new Account(
                Name = name,
                Industry = 'Education',
                AnnualRevenue = 2000000,
                Rating = 'Warm',
                Phone = '206-555-7890',
                Description = 'EdTech startup. Fast-growing, recently raised Series B. Looking for scalable CRM solution. Technical founder prefers API-first approach.',
                BillingCity = 'Seattle',
                BillingState = 'WA',
                Is_Gold_Client__c = false
            ));
        }
    }
}

if (!accounts.isEmpty()) {
    Database.SaveResult[] results = Database.insert(accounts, false);
    Integer successCount = 0;
    for (Integer i = 0; i < results.size(); i++) {
        if (results[i].isSuccess()) {
            successCount++;
        } else {
            System.debug('ERROR inserting Account ' + accounts[i].Name + ': ' + results[i].getErrors());
        }
    }
    System.debug('✓ Created ' + successCount + ' new Accounts');
}

// Build account map (include existing accounts)
Map<String, Id> accountMap = new Map<String, Id>();
for (Account a : [SELECT Id, Name FROM Account WHERE Name IN :accountNames]) {
    accountMap.put(a.Name, a.Id);
}

if (accountMap.isEmpty()) {
    System.debug('ERROR: No accounts found. Cannot create related records.');
    return;
}

// --- CONTACTS ---
List<String> contactEmails = new List<String>{
    'sarah.chen@acme.example.com',
    'mike.j@acme.example.com',
    'lisa.park@acme.example.com',
    'rwilliams@globaltech.example.com',
    'jmartinez@globaltech.example.com',
    'jwilson@sunrise.example.com',
    'afoster@sunrise.example.com',
    'dthompson@summit.example.com',
    'alex@edulearn.example.com',
    'priya@edulearn.example.com'
};

Map<String, Contact> existingContacts = new Map<String, Contact>();
for (Contact c : [SELECT Id, Email FROM Contact WHERE Email IN :contactEmails]) {
    existingContacts.put(c.Email, c);
}

if (CLEANUP_MODE && !existingContacts.isEmpty()) {
    delete existingContacts.values();
    System.debug('✓ Cleaned up ' + existingContacts.size() + ' existing Contacts');
    existingContacts.clear();
}

List<Contact> contacts = new List<Contact>();
if (!existingContacts.containsKey('sarah.chen@acme.example.com') && accountMap.containsKey('Acme Corporation')) {
    contacts.add(new Contact(FirstName = 'Sarah', LastName = 'Chen', Title = 'Chief Technology Officer', Email = 'sarah.chen@acme.example.com', Phone = '415-555-1001', Department = 'Engineering', AccountId = accountMap.get('Acme Corporation'), Description = 'Primary decision maker. Prefers technical discussions. Available Tuesdays and Thursdays.'));
}
if (!existingContacts.containsKey('mike.j@acme.example.com') && accountMap.containsKey('Acme Corporation')) {
    contacts.add(new Contact(FirstName = 'Mike', LastName = 'Johnson', Title = 'VP of Engineering', Email = 'mike.j@acme.example.com', Phone = '415-555-1002', Department = 'Engineering', AccountId = accountMap.get('Acme Corporation'), Description = 'Reports to Sarah. Handles day-to-day technical evaluation. Very responsive on Slack.'));
}
if (!existingContacts.containsKey('lisa.park@acme.example.com') && accountMap.containsKey('Acme Corporation')) {
    contacts.add(new Contact(FirstName = 'Lisa', LastName = 'Park', Title = 'Procurement Manager', Email = 'lisa.park@acme.example.com', Phone = '415-555-1003', Department = 'Finance', AccountId = accountMap.get('Acme Corporation'), Description = 'Handles contracts and purchasing. Needs 2 weeks notice for approvals.'));
}
if (!existingContacts.containsKey('rwilliams@globaltech.example.com') && accountMap.containsKey('GlobalTech Industries')) {
    contacts.add(new Contact(FirstName = 'Robert', LastName = 'Williams', Title = 'COO', Email = 'rwilliams@globaltech.example.com', Phone = '212-555-5001', Department = 'Operations', AccountId = accountMap.get('GlobalTech Industries'), Description = 'Executive sponsor. Only available for quarterly business reviews.'));
}
if (!existingContacts.containsKey('jmartinez@globaltech.example.com') && accountMap.containsKey('GlobalTech Industries')) {
    contacts.add(new Contact(FirstName = 'Jennifer', LastName = 'Martinez', Title = 'Supply Chain Director', Email = 'jmartinez@globaltech.example.com', Phone = '212-555-5002', Department = 'Operations', AccountId = accountMap.get('GlobalTech Industries'), Description = 'Main point of contact. Detailed oriented. Asks many technical questions.'));
}
if (!existingContacts.containsKey('jwilson@sunrise.example.com') && accountMap.containsKey('Sunrise Healthcare')) {
    contacts.add(new Contact(FirstName = 'Dr. James', LastName = 'Wilson', Title = 'Chief Medical Officer', Email = 'jwilson@sunrise.example.com', Phone = '312-555-9001', Department = 'Medical', AccountId = accountMap.get('Sunrise Healthcare'), Description = 'Key influencer. Concerned about clinical workflow disruption.'));
}
if (!existingContacts.containsKey('afoster@sunrise.example.com') && accountMap.containsKey('Sunrise Healthcare')) {
    contacts.add(new Contact(FirstName = 'Amanda', LastName = 'Foster', Title = 'IT Director', Email = 'afoster@sunrise.example.com', Phone = '312-555-9002', Department = 'IT', AccountId = accountMap.get('Sunrise Healthcare'), Description = 'Technical buyer. Responsible for integration and security review.'));
}
if (!existingContacts.containsKey('dthompson@summit.example.com') && accountMap.containsKey('Summit Financial Group')) {
    contacts.add(new Contact(FirstName = 'David', LastName = 'Thompson', Title = 'Managing Director', Email = 'dthompson@summit.example.com', Phone = '617-555-3001', Department = 'Executive', AccountId = accountMap.get('Summit Financial Group'), Description = 'Skeptical of new vendors. Requires extensive references.'));
}
if (!existingContacts.containsKey('alex@edulearn.example.com') && accountMap.containsKey('EduLearn Platform')) {
    contacts.add(new Contact(FirstName = 'Alex', LastName = 'Rivera', Title = 'CEO & Co-founder', Email = 'alex@edulearn.example.com', Phone = '206-555-7001', Department = 'Executive', AccountId = accountMap.get('EduLearn Platform'), Description = 'Technical background. Makes fast decisions. Prefers async communication.'));
}
if (!existingContacts.containsKey('priya@edulearn.example.com') && accountMap.containsKey('EduLearn Platform')) {
    contacts.add(new Contact(FirstName = 'Priya', LastName = 'Sharma', Title = 'Head of Product', Email = 'priya@edulearn.example.com', Phone = '206-555-7002', Department = 'Product', AccountId = accountMap.get('EduLearn Platform'), Description = 'Evaluates product fit. Very focused on user experience.'));
}

if (!contacts.isEmpty()) {
    Database.SaveResult[] results = Database.insert(contacts, false);
    Integer successCount = 0;
    for (Integer i = 0; i < results.size(); i++) {
        if (results[i].isSuccess()) {
            successCount++;
        } else {
            System.debug('ERROR inserting Contact ' + contacts[i].Email + ': ' + results[i].getErrors());
        }
    }
    System.debug('✓ Created ' + successCount + ' new Contacts');
}

// --- OPPORTUNITIES ---
List<String> opportunityNames = new List<String>{
    'Acme Corp - Enterprise Platform Deal',
    'GlobalTech - Supply Chain Module',
    'Sunrise Healthcare - Patient Engagement',
    'Summit Financial - CRM Replacement',
    'EduLearn - Startup Package'
};

Map<String, Opportunity> existingOpps = new Map<String, Opportunity>();
for (Opportunity o : [SELECT Id, Name FROM Opportunity WHERE Name IN :opportunityNames]) {
    existingOpps.put(o.Name, o);
}

if (CLEANUP_MODE && !existingOpps.isEmpty()) {
    delete existingOpps.values();
    System.debug('✓ Cleaned up ' + existingOpps.size() + ' existing Opportunities');
    existingOpps.clear();
}

List<Opportunity> opportunities = new List<Opportunity>();
Map<String, Id> oppMap = new Map<String, Id>();

if (!existingOpps.containsKey('Acme Corp - Enterprise Platform Deal') && accountMap.containsKey('Acme Corporation')) {
    opportunities.add(new Opportunity(
        Name = 'Acme Corp - Enterprise Platform Deal',
        AccountId = accountMap.get('Acme Corporation'),
        Amount = 250000,
        StageName = 'Proposal/Price Quote',
        CloseDate = Date.today().addDays(30),
        Probability = 75,
        Description = 'Enterprise license for 500 users. Competing against Competitor X. Price is main concern. Need to demonstrate ROI.',
        NextStep = 'Send revised proposal with volume discount'
    ));
}
if (!existingOpps.containsKey('GlobalTech - Supply Chain Module') && accountMap.containsKey('GlobalTech Industries')) {
    opportunities.add(new Opportunity(
        Name = 'GlobalTech - Supply Chain Module',
        AccountId = accountMap.get('GlobalTech Industries'),
        Amount = 180000,
        StageName = 'Negotiation/Review',
        CloseDate = Date.today().addDays(45),
        Probability = 60,
        Description = 'Supply chain optimization module. Legal is reviewing contract. Need to address data residency requirements.',
        NextStep = 'Schedule call with legal team'
    ));
}
if (!existingOpps.containsKey('Sunrise Healthcare - Patient Engagement') && accountMap.containsKey('Sunrise Healthcare')) {
    opportunities.add(new Opportunity(
        Name = 'Sunrise Healthcare - Patient Engagement',
        AccountId = accountMap.get('Sunrise Healthcare'),
        Amount = 320000,
        StageName = 'Qualification',
        CloseDate = Date.today().addDays(90),
        Probability = 40,
        Description = 'Patient engagement platform for 3 hospitals. HIPAA BAA required. Pilot program proposed for one facility first.',
        NextStep = 'Complete security questionnaire'
    ));
}
if (!existingOpps.containsKey('Summit Financial - CRM Replacement') && accountMap.containsKey('Summit Financial Group')) {
    opportunities.add(new Opportunity(
        Name = 'Summit Financial - CRM Replacement',
        AccountId = accountMap.get('Summit Financial Group'),
        Amount = 500000,
        StageName = 'Needs Analysis',
        CloseDate = Date.today().addDays(180),
        Probability = 20,
        Description = 'Replace legacy CRM. Complex data migration required. Client has concerns from previous failed implementation.',
        NextStep = 'Arrange reference call with similar financial services client'
    ));
}
if (!existingOpps.containsKey('EduLearn - Startup Package') && accountMap.containsKey('EduLearn Platform')) {
    opportunities.add(new Opportunity(
        Name = 'EduLearn - Startup Package',
        AccountId = accountMap.get('EduLearn Platform'),
        Amount = 45000,
        StageName = 'Proposal/Price Quote',
        CloseDate = Date.today().addDays(14),
        Probability = 85,
        Description = 'Startup tier license. Fast decision expected. Requested API documentation and sandbox access.',
        NextStep = 'Provide sandbox credentials'
    ));
}

if (!opportunities.isEmpty()) {
    Database.SaveResult[] results = Database.insert(opportunities, false);
    Integer successCount = 0;
    for (Integer i = 0; i < results.size(); i++) {
        if (results[i].isSuccess()) {
            successCount++;
            oppMap.put(opportunities[i].Name, opportunities[i].Id);
        } else {
            System.debug('ERROR inserting Opportunity ' + opportunities[i].Name + ': ' + results[i].getErrors());
        }
    }
    System.debug('✓ Created ' + successCount + ' new Opportunities');
}

// Build complete opportunity map (include existing)
for (Opportunity o : [SELECT Id, Name FROM Opportunity WHERE Name IN :opportunityNames]) {
    oppMap.put(o.Name, o.Id);
}

// --- CASES (Support Tickets) ---
List<String> caseSubjects = new List<String>{
    'API rate limiting issues during peak hours',
    'Request for custom report template',
    'SSO configuration assistance needed',
    'HIPAA compliance documentation request'
};

Map<String, Case> existingCases = new Map<String, Case>();
for (Case c : [SELECT Id, Subject FROM Case WHERE Subject IN :caseSubjects]) {
    existingCases.put(c.Subject, c);
}

if (CLEANUP_MODE && !existingCases.isEmpty()) {
    delete existingCases.values();
    System.debug('✓ Cleaned up ' + existingCases.size() + ' existing Cases');
    existingCases.clear();
}

List<Case> cases = new List<Case>();
if (!existingCases.containsKey('API rate limiting issues during peak hours') && accountMap.containsKey('Acme Corporation')) {
    cases.add(new Case(
        AccountId = accountMap.get('Acme Corporation'),
        Subject = 'API rate limiting issues during peak hours',
        Description = 'Customer reports 429 errors between 9-11 AM PST. Affecting their data sync jobs. Need to review their API usage patterns and potentially increase limits.',
        Status = 'New',
        Priority = 'High',
        Origin = 'Email'
    ));
}
if (!existingCases.containsKey('Request for custom report template') && accountMap.containsKey('GlobalTech Industries')) {
    cases.add(new Case(
        AccountId = accountMap.get('GlobalTech Industries'),
        Subject = 'Request for custom report template',
        Description = 'Customer needs a custom supply chain report showing inventory levels across all 3 warehouses. Standard reports do not meet their needs.',
        Status = 'Working',
        Priority = 'Medium',
        Origin = 'Phone'
    ));
}
if (!existingCases.containsKey('SSO configuration assistance needed') && accountMap.containsKey('Acme Corporation')) {
    cases.add(new Case(
        AccountId = accountMap.get('Acme Corporation'),
        Subject = 'SSO configuration assistance needed',
        Description = 'Setting up Okta SSO integration. Getting SAML assertion errors. Customer IT team available Thursday for troubleshooting session.',
        Status = 'Working',
        Priority = 'Medium',
        Origin = 'Web'
    ));
}
if (!existingCases.containsKey('HIPAA compliance documentation request') && accountMap.containsKey('Sunrise Healthcare')) {
    cases.add(new Case(
        AccountId = accountMap.get('Sunrise Healthcare'),
        Subject = 'HIPAA compliance documentation request',
        Description = 'Customer security team requesting updated SOC 2 report and HIPAA compliance documentation for their annual audit.',
        Status = 'New',
        Priority = 'High',
        Origin = 'Email'
    ));
}

if (!cases.isEmpty()) {
    Database.SaveResult[] results = Database.insert(cases, false);
    Integer successCount = 0;
    for (Integer i = 0; i < results.size(); i++) {
        if (results[i].isSuccess()) {
            successCount++;
        } else {
            System.debug('ERROR inserting Case ' + cases[i].Subject + ': ' + results[i].getErrors());
        }
    }
    System.debug('✓ Created ' + successCount + ' new Cases');
}

// --- TASKS ---
List<String> taskSubjects = new List<String>{
    'Follow up on proposal feedback',
    'Send case study to GlobalTech',
    'Prepare security questionnaire responses',
    'Schedule demo for EduLearn team',
    'Quarterly business review prep'
};

Map<String, Task> existingTasks = new Map<String, Task>();
for (Task t : [SELECT Id, Subject FROM Task WHERE Subject IN :taskSubjects]) {
    existingTasks.put(t.Subject, t);
}

if (CLEANUP_MODE && !existingTasks.isEmpty()) {
    delete existingTasks.values();
    System.debug('✓ Cleaned up ' + existingTasks.size() + ' existing Tasks');
    existingTasks.clear();
}

List<Task> tasks = new List<Task>();
if (!existingTasks.containsKey('Follow up on proposal feedback') && oppMap.containsKey('Acme Corp - Enterprise Platform Deal')) {
    tasks.add(new Task(
        Subject = 'Follow up on proposal feedback',
        WhatId = oppMap.get('Acme Corp - Enterprise Platform Deal'),
        Description = 'Sarah mentioned she would review proposal by EOD Monday. Follow up to address any questions.',
        Status = 'Not Started',
        Priority = 'High',
        ActivityDate = Date.today().addDays(2)
    ));
}
if (!existingTasks.containsKey('Send case study to GlobalTech') && oppMap.containsKey('GlobalTech - Supply Chain Module')) {
    tasks.add(new Task(
        Subject = 'Send case study to GlobalTech',
        WhatId = oppMap.get('GlobalTech - Supply Chain Module'),
        Description = 'Jennifer requested manufacturing case study. Send the AutoParts Inc success story.',
        Status = 'Not Started',
        Priority = 'Normal',
        ActivityDate = Date.today().addDays(1)
    ));
}
if (!existingTasks.containsKey('Prepare security questionnaire responses') && oppMap.containsKey('Sunrise Healthcare - Patient Engagement')) {
    tasks.add(new Task(
        Subject = 'Prepare security questionnaire responses',
        WhatId = oppMap.get('Sunrise Healthcare - Patient Engagement'),
        Description = 'Complete 50-page security questionnaire. Need input from InfoSec team. Deadline is next Friday.',
        Status = 'In Progress',
        Priority = 'High',
        ActivityDate = Date.today().addDays(5)
    ));
}
if (!existingTasks.containsKey('Schedule demo for EduLearn team') && oppMap.containsKey('EduLearn - Startup Package')) {
    tasks.add(new Task(
        Subject = 'Schedule demo for EduLearn team',
        WhatId = oppMap.get('EduLearn - Startup Package'),
        Description = 'Alex wants a technical demo focusing on API capabilities. Invite solutions engineer.',
        Status = 'Not Started',
        Priority = 'High',
        ActivityDate = Date.today()
    ));
}
if (!existingTasks.containsKey('Quarterly business review prep') && accountMap.containsKey('GlobalTech Industries')) {
    tasks.add(new Task(
        Subject = 'Quarterly business review prep',
        WhatId = accountMap.get('GlobalTech Industries'),
        Description = 'Prepare QBR deck for Robert Williams. Include usage metrics, support ticket summary, and roadmap updates.',
        Status = 'Not Started',
        Priority = 'Normal',
        ActivityDate = Date.today().addDays(14)
    ));
}

if (!tasks.isEmpty()) {
    Database.SaveResult[] results = Database.insert(tasks, false);
    Integer successCount = 0;
    for (Integer i = 0; i < results.size(); i++) {
        if (results[i].isSuccess()) {
            successCount++;
        } else {
            System.debug('ERROR inserting Task ' + tasks[i].Subject + ': ' + results[i].getErrors());
        }
    }
    System.debug('✓ Created ' + successCount + ' new Tasks');
}

System.debug('CRM seed data complete!');

