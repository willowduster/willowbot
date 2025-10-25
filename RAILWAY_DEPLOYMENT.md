# Railway.app Deployment Guide

This guide will walk you through deploying WillowBot to Railway.app for free hosting.

## Prerequisites

- GitHub account with WillowBot repository
- Discord bot token and OAuth2 credentials
- Railway.app account (sign up at https://railway.app)

## Step 1: Prepare Your Repository

Your repository is already configured with:
- ✅ `Dockerfile` for containerization
- ✅ `docker-compose.yml` for local development
- ✅ `requirements.txt` with all dependencies
- ✅ Environment variable configuration

## Step 2: Create a Railway Project

1. Go to https://railway.app
2. Click **"Start a New Project"**
3. Choose **"Deploy from GitHub repo"**
4. Select your **willowbot** repository
5. Railway will automatically detect your Dockerfile and begin deployment

## Step 3: Configure Environment Variables

After your project is created:

1. Click on your deployment
2. Go to **Variables** tab
3. Add the following environment variables:

```env
# Required - Discord Bot
DISCORD_TOKEN=your_discord_bot_token_here
ADMIN_USER_ID=your_discord_user_id_here

# Required - OAuth2 Authentication
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
DISCORD_REDIRECT_URI=https://your-app-name.up.railway.app/callback
FLASK_SECRET_KEY=your_generated_secret_key

# Optional - Database Path (Railway provides persistent storage)
DATABASE_PATH=/app/data/willowbot.db
```

**Important Notes:**
- Replace `your-app-name.up.railway.app` with your actual Railway URL (you'll see this in the deployment)
- Generate `FLASK_SECRET_KEY` using: `python -c "import secrets; print(secrets.token_hex(32))"`
- Get your Discord User ID by enabling Developer Mode in Discord, then right-clicking your username

## Step 4: Add Production OAuth2 Redirect

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your WillowBot application
3. Navigate to **OAuth2** → **General**
4. Under **Redirects**, click **Add Redirect**
5. Add: `https://your-app-name.up.railway.app/callback`
6. Click **Save Changes**

**Keep your existing localhost redirect** for local development!

## Step 5: Configure Persistent Storage

Railway provides persistent volumes for your database:

1. In your Railway project, click **"+ New"**
2. Select **"Volume"**
3. Set mount path: `/app/data`
4. Click **"Add"**
5. Connect the volume to your service

This ensures your SQLite database persists across deployments.

## Step 6: Deploy!

1. Click **"Deploy"** in Railway
2. Wait for the build to complete (usually 2-3 minutes)
3. Once deployed, you'll get a URL like: `https://your-app-name.up.railway.app`
4. Visit the URL to test your deployment!

## Step 7: Verify Deployment

Test the following:

- [ ] Web dashboard loads at your Railway URL
- [ ] Discord login redirects work correctly
- [ ] Admin login shows full dashboard
- [ ] Discord bot is online and responding to commands
- [ ] Combat and quests work in Discord
- [ ] Player data persists after redeployment

## Monitoring & Logs

**View Logs:**
1. Click on your service in Railway
2. Go to **"Deployments"** tab
3. Click on the latest deployment
4. View real-time logs

**Check Health:**
- Railway automatically monitors your app
- View metrics in the **"Metrics"** tab
- Set up alerts for downtime

## Railway Free Tier

**What you get:**
- $5 USD credit per month
- Enough for a small-medium Discord bot
- Persistent storage included
- Automatic deployments from GitHub
- Custom domain support

**Usage Tips:**
- Monitor your usage in Railway dashboard
- Bot runs 24/7 within credit limits
- Optimize if you exceed free tier

## Automatic Deployments

Railway automatically deploys when you push to GitHub:

1. Make changes to your code
2. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Your changes"
   git push
   ```
3. Railway automatically detects the push
4. New deployment starts automatically
5. Zero downtime with rolling deployments

## Custom Domain (Optional)

Want a custom domain instead of `*.railway.app`?

1. In Railway project, go to **Settings**
2. Click **"Generate Domain"** or **"Custom Domain"**
3. Follow instructions to point your domain to Railway
4. Update `DISCORD_REDIRECT_URI` to use your custom domain

## Troubleshooting

### "OAuth2 redirect mismatch" error
- Check that `DISCORD_REDIRECT_URI` matches exactly what's in Discord Developer Portal
- Ensure the URL includes `https://` (not `http://`)
- Verify there are no trailing slashes

### Bot not responding in Discord
- Check Railway logs for errors
- Verify `DISCORD_TOKEN` is correct
- Ensure bot has all required permissions in your Discord server

### Database resets after deployment
- Make sure you've attached a persistent volume
- Verify volume is mounted to `/app/data`
- Check `DATABASE_PATH` environment variable

### "Failed to get access token" error
- Verify `DISCORD_CLIENT_SECRET` is correct
- Check that the client secret hasn't expired
- Ensure OAuth2 redirect URI is added in Discord Developer Portal

### Out of Railway credits
- Check your usage in Railway dashboard
- Optimize Docker image size
- Consider upgrading to a paid plan for higher usage

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DISCORD_TOKEN` | Yes | Your Discord bot token | `MTk4NjIyNDgzNDcxOTI1MjQ4...` |
| `ADMIN_USER_ID` | Yes | Your Discord user ID | `123456789012345678` |
| `DISCORD_CLIENT_ID` | Yes | Discord OAuth2 client ID | `987654321098765432` |
| `DISCORD_CLIENT_SECRET` | Yes | Discord OAuth2 client secret | `abcdef123456...` |
| `DISCORD_REDIRECT_URI` | Yes | OAuth2 callback URL | `https://app.railway.app/callback` |
| `FLASK_SECRET_KEY` | Yes | Flask session encryption key | `a1b2c3d4e5f6...` |
| `DATABASE_PATH` | No | SQLite database location | `/app/data/willowbot.db` |

## Security Best Practices

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Rotate secrets regularly** - Update OAuth2 secrets periodically
3. **Use HTTPS only** - Railway provides this automatically
4. **Monitor access logs** - Check for suspicious activity
5. **Keep dependencies updated** - Run `pip list --outdated` regularly

## Next Steps

Once deployed:

1. **Test thoroughly** - Try all bot commands and web features
2. **Monitor usage** - Keep an eye on Railway credits
3. **Set up backups** - Periodically download your database
4. **Share with users** - Invite players to your Discord server
5. **Iterate** - Continue improving based on user feedback

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- WillowBot Issues: https://github.com/willowduster/willowbot/issues

## Success! 🎉

Your WillowBot is now live and accessible to players worldwide!

Players can:
- Join your Discord server
- Use `!w start` to create their character
- Battle enemies and complete quests
- Login to the web dashboard to view their stats

Admins can:
- Monitor all players via web dashboard
- View bot status and metrics
- Manage the bot remotely

Enjoy your deployed Discord RPG bot! 🎮✨
