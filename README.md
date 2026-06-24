# 💸 PS1 Bhargav Expense Tracker

A full stack expense tracker web application built with FastAPI , vanilla HTML/CSS/JS.

Live URL:-

- **Frontend:** https://frontend-production-016b.up.railway.app
- **Backend API:** https://backend-production-0b67.up.railway.app/docs

 Features:-

- User authentication (signup/login with JWT tokens)
- Add, edit, and delete expenses
- Category-wise summary with visual bars
- Persistent storage with PostgreSQL
- Each user has their own private expense data
- Stays logged in for 30 days (remember me)
- User can log expenses at any time , helps differentiate expenses of seperate periods

 ##Tech Stack:-

 - Frontend - HTML, CSS, JavaScript
 - Backend - Python, FastAPI 
 - Database - PostgreSQL 
 - Auth - JWT tokens, bcrypt 
 - Hosting - Railway 

How to Run Locally:-

### Backend
```bash
cd backend
python main.py
```
Backend runs on `http://localhost:5000`
API docs available at `http://localhost:5000/docs`

### Frontend
```bash
cd frontend
python -m http.server 3000
```
Open `http://localhost:3000` in your browser.
