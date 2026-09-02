-- ==========================================================
-- TicketGenie Synthetic Test Data
-- Initial Tickets
-- ==========================================================

INSERT INTO dbo.Tickets (
    ticket_number,
    created_by_user_id,
    assigned_to_user_id,
    department,
    category,
    title,
    description,
    status,
    priority,
    is_anonymous,
    ai_summary,
    ai_suggested_response,
    ai_priority_confidence
)
VALUES
    (
        'TG-2026-000001',
        (SELECT user_id FROM dbo.Users WHERE username = 'employee.demo'),
        (SELECT user_id FROM dbo.Users WHERE username = 'it.agent'),
        'IT',
        'VPN',
        'Unable to connect to company VPN',
        'The VPN client shows a connection timeout when I try to sign in from home.',
        'IN_PROGRESS',
        'P3',
        0,
        'Employee cannot connect to the company VPN from home due to a connection timeout.',
        'Restart the VPN client, verify internet access, and retry using the approved company VPN profile.',
        0.9200
    ),
    (
        'TG-2026-000002',
        (SELECT user_id FROM dbo.Users WHERE username = 'employee.demo'),
        (SELECT user_id FROM dbo.Users WHERE username = 'hr.agent'),
        'HR',
        'Leave',
        'Question about parental leave eligibility',
        'I would like to understand the eligibility rules and required documents for parental leave.',
        'OPEN',
        'P4',
        0,
        'Employee is requesting information about parental leave eligibility and documentation.',
        'Review the parental leave policy and provide the eligibility criteria and required documentation.',
        0.8800
    ),
    (
        'TG-2026-000003',
        (SELECT user_id FROM dbo.Users WHERE username = 'employee.demo'),
        (SELECT user_id FROM dbo.Users WHERE username = 'hr.agent'),
        'HR',
        'Workplace Concern',
        'Confidential workplace concern',
        'I would like to report a sensitive workplace concern and request confidential follow-up.',
        'OPEN',
        'P2',
        1,
        'Anonymous employee submitted a sensitive workplace concern requiring confidential HR review.',
        NULL,
        0.9600
    ),
    (
        'TG-2026-000004',
        (SELECT user_id FROM dbo.Users WHERE username = 'employee.demo'),
        NULL,
        'IT',
        'Software Access',
        'Request access to design software',
        'I need access to the approved design software for an upcoming project.',
        'OPEN',
        'P4',
        0,
        'Employee is requesting access to approved design software for project work.',
        'Confirm manager approval and verify that an available software license can be assigned.',
        0.8500
    ),
    (
        'TG-2026-000005',
        (SELECT user_id FROM dbo.Users WHERE username = 'employee.demo'),
        (SELECT user_id FROM dbo.Users WHERE username = 'it.agent'),
        'IT',
        'Network',
        'Office network unavailable',
        'Multiple employees on the third floor cannot connect to the office network.',
        'IN_PROGRESS',
        'P1',
        0,
        'A network outage is affecting multiple employees on the third floor.',
        'Escalate immediately to the network support team and begin outage diagnostics.',
        0.9900
    ),
    (
        'TG-2026-000006',
        (SELECT user_id FROM dbo.Users WHERE username = 'admin.dc3b'),
        (SELECT user_id FROM dbo.Users WHERE username = 'it.agent'),
        'IT',
        'VPN',
        'VPN Connection Issue for Admin User',
        'Unable to connect to internal VPN network from remote office.',
        'OPEN',
        'P2',
        0,
        'Admin user reported a VPN connection issue from remote office.',
        'Verify VPN certificate and reset remote access profile.',
        0.9500
    );
GO
