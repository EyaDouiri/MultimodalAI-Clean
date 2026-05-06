# 🧪 Test Guide: Dynamic Levels & Admin Dashboard

## Quick Start Testing

### 1️⃣ Backend Test - Level Calculation

Run the test script to verify level calculation logic:

```bash
cd c:\Users\eyaen\Desktop\PI
python test_dynamic_levels.py
```

Expected output:
```
============================================================
Testing Dynamic Level Calculation
============================================================

Test User: Test Niveau (test_niveau@example.com)
Created: True

Using medicament: [First medicament in DB]

Test 1: No assignments
  Expected: débutant
  Actual: débutant
  ✓ Passed

Test 2: Average score < 65 (scores: 50, 60, 70)
  Average score: 60.0
  Expected: débutant
  Actual: débutant
  ✓ Passed

Test 3: Average score 65-85 (scores: 70, 80, 90)
  Average score: 80.0
  Expected: intermédiaire
  Actual: intermédiaire
  ✓ Passed

Test 4: Average score >= 85 (scores: 85, 90, 95)
  Average score: 90.0
  Expected: confirmé
  Actual: confirmé
  ✓ Passed

============================================================
✓ All tests passed!
============================================================
```

### 2️⃣ Frontend Integration Test

#### A. Start Django Backend
```bash
cd c:\Users\eyaen\Desktop\PI\alia_backend
python manage.py runserver 127.0.0.1:8000
```

#### B. Start Flask Avatar Server
```bash
cd c:\Users\eyaen\Desktop\PI
python avatar_server.py
```

#### C. Start React Frontend
```bash
cd c:\Users\eyaen\Desktop\PI\alia-frontend
npm run dev
```

#### D. Test Admin Dashboard
1. Open browser: http://localhost:3000
2. Login as admin (role='admin')
3. Navigate to `/admin` 
4. Verify dashboard loads with:
   - ✓ Sidebar navigation (Délégués, Assignations)
   - ✓ Stats cards showing counts
   - ✓ Delegue grid with level badges
   - ✓ Color-coded levels (red/orange/green)

### 3️⃣ Feature Testing

#### Test A: Delegue Level Display
1. Login as delegue
2. Go to `/delegue` (Home page)
3. Verify niveau badge shows under name
4. Colors should match admin dashboard

#### Test B: Edit Assignment Scores
1. As admin, go to `/admin`
2. Click "Assignations" tab
3. Click "✏️ Edit" on any assignment
4. Change scores and click "Mettre à jour"
5. Verify:
   - ✓ Modal closes
   - ✓ Table updates with new scores
   - ✓ Score global auto-calculated
   - ✓ Delegue's niveau recalculates

#### Test C: Delete Assignment
1. As admin, go to `/admin`
2. Click "Assignations" tab
3. Click "🗑️ Delete" on any assignment
4. Confirm deletion
5. Verify:
   - ✓ Assignment removed from table
   - ✓ Delegue's stats recalculate
   - ✓ Niveau updates if needed

#### Test D: Filter Delegues
1. As admin, go to `/admin`
2. Search by name in search box
3. Filter by niveau dropdown
4. Verify results filter correctly

#### Test E: Filter Assignments
1. As admin, click "Assignations"
2. Search by delegue name or medicament
3. Filter by statut dropdown
4. Verify results filter correctly

### 4️⃣ API Endpoint Testing

Use Postman or curl to test API changes:

#### Get Profile with Calculated Level
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://127.0.0.1:8000/api/delegue/profil
```

Response should include:
```json
{
  "id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "niveau": "intermédiaire",  ← CALCULATED DYNAMICALLY
  "assignments": [...]
}
```

#### Get Admin Delegues List
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://127.0.0.1:8000/api/admin/delegues
```

Response should show:
```json
{
  "ok": true,
  "delegues": [
    {
      "id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "niveau": "confirmé",  ← CALCULATED DYNAMICALLY
      "nb_produits": 5,
      "assignments": [...]
    }
  ]
}
```

### 5️⃣ Smoke Test Checklist

- [ ] Django server starts without errors
- [ ] React frontend starts without errors
- [ ] Flask avatar server starts
- [ ] Can login as delegue
- [ ] Can login as admin
- [ ] Admin dashboard loads
- [ ] Delegue sees level badge
- [ ] Can edit assignment scores
- [ ] Can delete assignments
- [ ] Search/filter works
- [ ] Modals open/close correctly
- [ ] Data persists after page reload

## 📊 Expected Behavior

### Level Colors
| Level | Color | Background |
|-------|-------|------------|
| Débutant | Red (#fca5a5) | rgba(239,68,68,0.15) |
| Intermédiaire | Orange (#fbbf24) | rgba(245,158,11,0.15) |
| Confirmé | Green (#6ee7b7) | rgba(16,185,129,0.15) |

### Level Thresholds
| Range | Level |
|-------|-------|
| < 65 | Débutant |
| 65-85 | Intermédiaire |
| ≥ 85 | Confirmé |

### Score Global Calculation
```
score_global = round((module1 + module2 + module3) / 3)
```

## 🐛 Troubleshooting

### Issue: Niveau doesn't update
**Solution**: Verify `calculate_niveau()` is called:
```python
# In models.py, User model should have:
def calculate_niveau(self):
    # ... implementation
```

### Issue: Admin dashboard doesn't load
**Solution**: Check:
1. Token is in localStorage
2. Role is 'admin'
3. Django backend is running on 127.0.0.1:8000
4. CORS headers are configured

### Issue: Modals not working
**Solution**: Ensure `editingAssignment` state is managed in AdminDashboard.jsx

### Issue: Filters not filtering
**Solution**: Check that filter state updates: `filters.delegueSearch`, etc.

## 📝 Performance Notes

- Level calculation happens at API call time (efficient)
- No caching needed - always real-time
- Dashboard loads full delegue list (consider pagination for 100+ users)
- Filters run client-side (good for < 1000 items)

## 🚀 Production Checklist

- [ ] Add error handling for failed API calls
- [ ] Add loading spinners while data fetches
- [ ] Add success toast notifications
- [ ] Test with real data (100+ delegues)
- [ ] Test responsive design on mobile
- [ ] Add analytics/logging
- [ ] Performance testing
- [ ] Accessibility audit (WCAG AA)
- [ ] Security audit (XSS, CSRF)
- [ ] Add pagination for large datasets

---

**Need Help?**
1. Check Django logs: `python manage.py runserver`
2. Check browser console: F12 → Console tab
3. Check Flask logs: `python avatar_server.py`
4. Verify database: `sqlite3 db.sqlite3` → `.tables`
