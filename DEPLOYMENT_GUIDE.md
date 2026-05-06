# 🚀 Deployment Guide: Dynamic Levels & Admin Dashboard

## Pre-Deployment Checklist

### 1. Verify Files
```bash
# Backend changes
dir alia_backend\api\models.py       ✓ calculate_niveau() added
dir alia_backend\api\views.py         ✓ Use calculate_niveau() in endpoints

# Frontend changes
dir alia-frontend\src\App.jsx         ✓ Import AdminDashboard
dir alia-frontend\src\pages\AdminDashboard.jsx    ✓ NEW component
dir alia-frontend\src\pages\DeieguePages.jsx      ✓ Show niveau badge
dir alia-frontend\src\styles\admin-dashboard.css  ✓ NEW styles

# Documentation
dir TEST_GUIDE.md                   ✓ Testing procedures
dir DYNAMIC_LEVELS_AND_ADMIN_DASHBOARD.md  ✓ Feature docs
```

### 2. Verify Python Syntax
```bash
cd c:\Users\eyaen\Desktop\PI
python -m py_compile alia_backend/api/models.py
python -m py_compile alia_backend/api/views.py
```

Expected: No output = No errors ✓

### 3. Test Database
```bash
# Verify database exists
dir alia_backend\db.sqlite3
```

Expected: File exists ✓

## Deployment Steps

### Phase 1: Backend Deployment

No database migrations needed! The User model already has `niveau` field.

1. Verify Django starts:
```bash
cd c:\Users\eyaen\Desktop\PI\alia_backend
python manage.py check
```

Expected:
```
System check identified no issues (0 silenced).
```

2. Test API endpoints:
```bash
# In separate terminal, test the endpoints
curl -X GET http://127.0.0.1:8000/api/admin/delegues \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Phase 2: Frontend Deployment

1. Install dependencies (if needed):
```bash
cd c:\Users\eyaen\Desktop\PI\alia-frontend
npm install
```

2. Build for production:
```bash
npm run build
```

Expected: `dist/` folder created with all assets

3. Test dev server:
```bash
npm run dev
```

Expected: Server starts on http://localhost:3000

### Phase 3: Testing

Run automated tests:
```bash
cd c:\Users\eyaen\Desktop\PI
python test_dynamic_levels.py
```

Expected: All 4 tests pass ✓

### Phase 4: Manual Testing

Follow [TEST_GUIDE.md](TEST_GUIDE.md) checklist

## Production Deployment

### Option 1: Docker (Recommended)

1. Build images:
```bash
# Backend
docker build -f Dockerfile.backend -t alia-backend:latest .

# Frontend
docker build -f Dockerfile.frontend -t alia-frontend:latest .
```

2. Run containers:
```bash
docker-compose up -d
```

### Option 2: Traditional Server

1. Copy files to server:
```bash
# Backend
scp -r alia_backend/ user@server:/app/alia_backend

# Frontend build
scp -r alia-frontend/dist/ user@server:/var/www/alia
```

2. Run services:
```bash
# Backend
cd /app/alia_backend
gunicorn -w 4 -b 0.0.0.0:8000 alia_backend.asgi:application

# Frontend - serve with nginx
# config: proxy_pass http://localhost:3000;
```

## Rollback Plan

If issues occur:

### Rollback Step 1: Revert Backend
```bash
# Restore previous API version
git checkout HEAD~1 alia_backend/api/views.py
git checkout HEAD~1 alia_backend/api/models.py
```

### Rollback Step 2: Revert Frontend
```bash
# Restore previous AdminPage
git checkout HEAD~1 alia-frontend/src/App.jsx
git checkout HEAD~1 alia-frontend/src/pages/DeieguePages.jsx
```

### Rollback Step 3: Restart Services
```bash
# Django
python manage.py runserver

# React
npm run dev
```

## Verification Checklist

After deployment, verify:

- [ ] Django backend starts without errors
- [ ] React frontend starts without errors
- [ ] Admin can login and access `/admin`
- [ ] Admin dashboard loads with stats
- [ ] Delegue sees niveau badge
- [ ] Can edit assignment scores
- [ ] Can delete assignments
- [ ] Niveau updates when scores change
- [ ] Filters work in admin dashboard
- [ ] Mobile responsive works
- [ ] No console errors in browser
- [ ] API responds with correct data

## Performance Monitoring

### Monitor Django
```bash
# Check query count and execution time
python manage.py shell

>>> from django.db import connection
>>> from django.test.utils import CaptureQueriesContext
>>> with CaptureQueriesContext(connection) as ctx:
>>>     # Run your API call
>>>     pass
>>> len(ctx)  # Number of queries
```

### Monitor React
Use React DevTools in browser to check component renders.

### Monitor API Response Times
```bash
# Time the endpoint
curl -w "@curl-format.txt" -o /dev/null -s http://127.0.0.1:8000/api/admin/delegues
```

## Troubleshooting Production Issues

### Issue: 500 Error on /admin/delegues

**Possible Cause**: calculate_niveau() not defined

**Fix**:
```bash
# Check models.py has the method
grep -n "def calculate_niveau" alia_backend/api/models.py
```

### Issue: Admin Dashboard Doesn't Load

**Possible Cause**: Token not in localStorage

**Fix**:
```javascript
// In browser console
localStorage.setItem('token', 'YOUR_TOKEN');
localStorage.setItem('role', 'admin');
```

### Issue: Niveau Badge Wrong Color

**Possible Cause**: CSS not loaded

**Fix**:
```bash
# Rebuild frontend
npm run build

# Clear browser cache
# Ctrl+Shift+Delete in Chrome
```

### Issue: API Returns Wrong Niveau

**Possible Cause**: calculate_niveau() not called

**Fix**:
```bash
# Check views.py uses calculate_niveau()
grep -n "calculate_niveau()" alia_backend/api/views.py
```

## Monitoring & Alerts

Set up alerts for:

1. **API Response Time** > 1 second
2. **Database Errors** in logs
3. **Frontend Errors** in browser console
4. **Failed Authentication** attempts

## Documentation Links

- [Feature Documentation](DYNAMIC_LEVELS_AND_ADMIN_DASHBOARD.md)
- [Testing Guide](TEST_GUIDE.md)
- [API Reference](README_LLM.md)

## Support & Questions

**Email**: admin@alia.local
**Slack**: #alia-dev
**Wiki**: https://wiki.alia.local

---

**Deployed By**: [Your Name]
**Date**: [Deployment Date]
**Version**: 2.1.0
**Status**: ✓ Production Ready
