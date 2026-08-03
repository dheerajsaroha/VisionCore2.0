# VisionCore v2.0 — Manual Testing Credentials

Generated: 2026-07-24T06:49:41.925797+00:00
Password: `Vision@123`

## Credential Table

| Role                   | Username             | Email                               | Password     | Organization         | Subscription Plan | Status   |
| ---------------------- | -------------------- | ----------------------------------- | ------------ | -------------------- | ---------------- | -------- |
| OrgAdmin               | val_OrgAdmin_47b8    | orgadmin_val@test.local             | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgAdmin               | subval_OrgAdmin_885c | orgadmin_sub_val@test.local         | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgEmployee            | val_OrgEmployee_794a | emp_val@test.local                  | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgEmployee            | subval_OrgEmployee_9acb | emp_sub_val@test.local              | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgHR                  | val_OrgHR_1199       | hr_val@test.local                   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgIntern              | val_OrgIntern_d00e   | intern_val@test.local               | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgManager             | val_OrgManager_0e79  | mgr_val@test.local                  | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| OrgViewer              | val_OrgViewer_cbfb   | viewer_val@test.local               | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | elena.vasquez        | elena.vasquez@visioncore.com        | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | marcus.chen          | marcus.chen@visioncore.com          | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | sophia.patel         | sophia.patel@visioncore.com         | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | btcl220010159010gjust | btcl220010159010gjust@visioncore.com | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | testsuperadmin       | superadmin@test.com                 | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | nitinyogi12          | nitinyogi12@gmail.com               | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | ajaykumar45          | ajaykumar45@gmail.com               | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | muskan12             | muskan12@gmail.com                  | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | nitin43              | nitin43@gmail.com                   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | dheeraj2002          | dheeraj2002@gmail.com               | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | nitin12              | nitin12@gmail.com                   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | e2e_owner_1          | e2e_owner_1@example.com             | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | e2e_owner_2          | e2e_owner_2@example.com             | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | ph1_owner1           | ph1_owner1@example.com              | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | ph1_owner2           | ph1_owner2@example.com              | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | dheerajsaroha2892002 | dheerajsaroha2892002@gmail.com      | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | codex.qa.20260710    | codex.qa.20260710@example.com       | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | owner01              | owner01@visioncore-enterprise.com   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | owner02              | owner02@visioncore-enterprise.com   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | owner03              | owner03@visioncore-enterprise.com   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | owner04              | owner04@visioncore-enterprise.com   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | owner05              | owner05@visioncore-enterprise.com   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | superadmin           | superadmin@visioncore.local         | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | val_SuperAdmin_957c  | sa_val@test.local                   | Vision@123   | VisionCore Test Organization | Professional     | Active   |
| SuperAdmin             | subval_SuperAdmin_0f70 | sa_sub_val@test.local               | Vision@123   | VisionCore Test Organization | Professional     | Active   |

## API Testing Endpoints

### Authentication
```
POST /api/v1/auth/login      — Login (form data: username=<email>, password=<password>)
POST /api/v1/auth/refresh    — Refresh token
POST /api/v1/auth/logout     — Logout
```

### Current User
```
GET /api/v1/users/me
```

### Permissions
```
GET /api/v1/rbac/me/permissions
```

### Subscription
```
GET /api/v1/subscription/my/subscription
GET /api/v1/subscription/my/features
```

---
*33 accounts — password: `Vision@123`*
