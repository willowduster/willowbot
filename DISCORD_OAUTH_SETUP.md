# Discord OAuth2 Setup Guide

This guide will help you set up Discord OAuth2 authentication for the WillowBot web dashboard.

## Step 1: Get Your Discord Application Credentials

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your WillowBot application (or create a new one if you haven't already)
3. In the left sidebar, click on **OAuth2** → **General**

### Get Your Client ID and Secret

4. Copy the **Client ID** - this is your `DISCORD_CLIENT_ID`
5. Click **Reset Secret** to generate a new client secret
6. Copy the **Client Secret** - this is your `DISCORD_CLIENT_SECRET`
   - ⚠️ **Important**: Save this secret immediately! You won't be able to see it again.

## Step 2: Add Redirect URI

1. Still in the OAuth2 settings, scroll down to **Redirects**
2. Click **Add Redirect**
3. Add the following URLs:
   - For local development: `http://localhost:5000/callback`
   - For production: `https://your-domain.com/callback`
4. Click **Save Changes**

## Step 3: Update Your .env File

Add the following to your `.env` file:

```env
# Discord Bot Token (you already have this)
DISCORD_TOKEN=your_bot_token_here
ADMIN_USER_ID=your_discord_user_id_here

# Discord OAuth2 for Flask Web Dashboard
DISCORD_CLIENT_ID=your_client_id_from_step_1
DISCORD_CLIENT_SECRET=your_client_secret_from_step_1
DISCORD_REDIRECT_URI=http://localhost:5000/callback
FLASK_SECRET_KEY=generate_a_random_secret_key_here
```

### How to Get Your Discord User ID (ADMIN_USER_ID)

1. Open Discord
2. Go to **User Settings** → **Advanced**
3. Enable **Developer Mode**
4. Right-click your username anywhere and select **Copy User ID**
5. Paste this into `ADMIN_USER_ID`

### Generate a Flask Secret Key

Run this Python command to generate a secure secret key:

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and use it as your `FLASK_SECRET_KEY`.

## Step 4: Install Required Dependencies

Make sure you have the `requests` library installed:

```bash
pip install -r requirements.txt
```

Or specifically:

```bash
pip install requests>=2.31.0
```

## Step 5: Test the Login

1. Start your Flask app:
   ```bash
   python webservice/app.py
   ```
   Or with Docker:
   ```bash
   docker compose up
   ```

2. Navigate to `http://localhost:5000`
3. You should be redirected to the login page
4. Click **Login with Discord**
5. Authorize the application
6. You should be redirected back to the dashboard

## Authentication Flow

### For Admin Users (Your Discord ID)
- Full access to all dashboard features
- Can view all players, items, quests
- Can start/stop the bot
- Can reset player data

### For Regular Users (Other Discord IDs)
- Redirected to their own player page
- Can only view their own stats, inventory, quests, deaths
- Cannot access admin features
- Cannot view other players' data

## Production Deployment

When deploying to production (Railway, Render, etc.):

1. Update `DISCORD_REDIRECT_URI` in your environment variables:
   ```
   DISCORD_REDIRECT_URI=https://your-production-domain.com/callback
   ```

2. Add the production callback URL to your Discord OAuth2 settings:
   - Go to Discord Developer Portal → OAuth2 → Redirects
   - Add `https://your-production-domain.com/callback`

3. Make sure all environment variables are set in your hosting platform

## Security Notes

- ✅ Sessions are encrypted using Flask's secret key
- ✅ Only authenticated users can access the dashboard
- ✅ Admin privileges are verified on every protected route
- ✅ Non-admin users cannot access other players' data
- ✅ Client secrets are never exposed to the frontend
- ⚠️ Always use HTTPS in production
- ⚠️ Never commit your `.env` file to Git

## Troubleshooting

### "Discord OAuth2 not configured" Error
- Make sure `DISCORD_CLIENT_ID` is set in your `.env` file
- Restart the Flask application after adding environment variables

### "Authorization failed" Error
- Check that your redirect URI matches exactly (including protocol and port)
- Verify the redirect URI is added in Discord Developer Portal

### "Failed to get access token" Error
- Verify your `DISCORD_CLIENT_SECRET` is correct
- Make sure you copied the secret immediately after generating it

### Login loop or "Access denied" Error
- Make sure your `ADMIN_USER_ID` is set correctly
- Verify you're using your actual Discord user ID (numeric)
- Check that the user ID matches your Discord account

## Need Help?

If you encounter issues:
1. Check the Flask application logs for detailed error messages
2. Verify all environment variables are set correctly
3. Make sure the Discord application has the correct OAuth2 settings
4. Test with `http://localhost:5000` before deploying to production
