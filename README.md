# Custom CRM - Phase 1: Backend Setup

Welcome! You now have a working Flask backend for your CRM. This guide will walk you through setting it up.

## What You Have

- `app.py` - Your main Flask application with all the backend logic
- `requirements.txt` - List of Python packages to install

## Setup Instructions

### Step 1: Create a Project Folder

On your computer, create a new folder for this project. Inside Visual Studio Code, open that folder.

### Step 2: Install Flask

Open the terminal in VS Code (View → Terminal, or Ctrl+`).

Run this command:

```
pip install -r requirements.txt
```

This installs Flask and Flask-CORS (which lets your frontend talk to your backend).

### Step 3: Run the App

In the same terminal, run:

```
python app.py
```

You should see something like:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Great! Your backend is running.

### Step 4: Test It's Working

Open your web browser and go to:

```
http://localhost:5000/api/health
```

You should see:

```json
{
  "status": "CRM Backend is running!"
}
```

If you see that, you're good to go!

## What This Backend Does (Right Now)

Your `app.py` file has everything to handle:

### Contacts
- **GET** `/api/contacts` - Get all contacts
- **POST** `/api/contacts` - Create a new contact
- **GET** `/api/contacts/<id>` - Get one contact
- **PUT** `/api/contacts/<id>` - Update a contact
- **DELETE** `/api/contacts/<id>` - Delete a contact

### Deals
- **GET** `/api/deals` - Get all deals (with contact info)
- **POST** `/api/deals` - Create a new deal
- **PUT** `/api/deals/<id>` - Update a deal
- **DELETE** `/api/deals/<id>` - Delete a deal

### Revenue
- **GET** `/api/revenue` - Get forecast (open deals) + realized (closed deals) revenue

### Database
Your app automatically creates `crm.db` (a SQLite database) with two tables:
- `contacts` - stores name, email, phone, company
- `deals` - stores deal info, linked to contacts

## Understanding the Code (High Level)

**Don't worry if you don't understand everything yet.** Here's what's happening:

1. **Flask Setup** - Lines 1-3: Import libraries and create the app
2. **Database Connection** - Lines 8-13: Function to connect to the database
3. **Initialize Database** - Lines 15-47: Creates tables when app starts
4. **Routes** - Lines 50+: These are the endpoints (the URLs that do things)
   - Each route is decorated with `@app.route()`
   - `GET` means "give me data"
   - `POST` means "create new data"
   - `PUT` means "update data"
   - `DELETE` means "remove data"

## Next Steps

Once you confirm the health check works, let me know! We'll build the frontend (HTML/CSS/JavaScript) so you can actually *use* this through a web interface.

## Troubleshooting

**"Flask is not installed"**
- Run: `pip install Flask Flask-CORS`

**"Port 5000 is already in use"**
- Another app is using that port. Change the last line of `app.py` from `port=5000` to `port=5001`

**Database errors**
- Delete any `crm.db` file in your folder and restart the app. It will recreate the database.

---

Once you get this running, reply and we'll move to Phase 2!
