# GeneralBot

A multipurpose Discord bot with **grouped slash commands and classic prefix commands** for moderation, entertainment, social, rating, utility, economy, levels, and server configuration.

Slash commands are grouped, for example:

```text
/moderation ban
/fun trivia
/reaction kiss
/social marry
/rate rizz
/utility userinfo
/economy daily
/level rank
/config welcome
```

Classic prefix commands are available too, using `?`, `.`, `'`, `;`, or `!`:

```text
?ban @user spamming
.kick @user
'timeout @user 10m
;warn @user breaking the rules
?role add @user @Members
!mute @user 10m
```

The bot supports **both guild installs and user installs**. Fun, reaction, social, rate, utility, economy, and level commands work in DMs. Moderation and configuration commands explain that they need a server when used in DMs.

---

## Features

### Moderation

| Command | What it does |
| --- | --- |
| `/moderation ban` | Ban a user, optionally deleting recent messages |
| `/moderation unban` | Unban a user by ID or mention |
| `/moderation kick` | Kick a member |
| `/moderation timeout` | Time a member out with durations like `10m`, `2h`, or `7d` |
| `/moderation untimeout` | Remove a member's timeout |
| `/moderation warn` | Store a warning and DM the user |
| `/moderation warnings` | Show a user's latest warnings |
| `/moderation delwarn` | Delete a specific warning |
| `/moderation clearwarnings` | Clear every warning for a user |
| `/moderation purge` | Bulk delete messages (omit amount to delete all available in chunks), optionally filtered by user |
| `/moderation purgechannel` | Delete and recreate a channel with the same properties |
| `/moderation slowmode` | Set or disable slowmode |
| `/moderation lock` | Stop `@everyone` from sending messages in a channel |
| `/moderation unlock` | Re-allow `@everyone` to send messages |
| `/moderation nickname` | Change or reset a member's nickname |

Moderation actions are recorded in the configured mod log. Bans, kicks, timeouts, and warnings also try to DM the affected user.

Every moderation command also has a prefix version: `?ban`, `?tempban`, `?kick`, `?timeout`, `?warn`, `?warnings`, `?purge`, `?slowmode`, `?lock`, `?unlock`, `?nickname`, and the rest. Use `?help` for the full list.

Many member-target prefix commands accept selectors: `all`, `others`, and `@role` (e.g. `?mute @role 10m`, `?kick others`, `?role add all @Members`). For `?mute` and `?tempban`, a duration of `0` (or `0s`/`0m`/`0h`/`0d`) means infinite/permanent.

### Prefix roles and utility commands

| Command | What it does |
| --- | --- |
| `?tempban <user\|selector> <duration> [reason]` | Temporarily ban a user (use `0` for infinite/permanent) |
| `?role <member\|selector> <role>` | Toggle a role (single target toggles; selectors add/remove per member) |
| `?role add <member\|selector> <role>` | Add a role |
| `?role remove <member\|selector> <role>` | Remove a role |
| `?role list [member]` | List server roles, or one member's roles |
| `?role info <role>` | Show role details |
| `?addrole` / `?removerole` | Short aliases for `?role add` / `?role remove` |
| `?createrole <name>` | Create a role |
| `?delrole <role>` | Delete a role |
| `?rolecolor <role> <color>` | Change a role's color |
| `?setname <member\|selector> [nickname]` | Change or reset nickname(s) |
| `?setservername <name>` | Change the server name |
| `?mute <member\|selector> [duration] [reason]` | Add the `Muted` role (creates/configures if missing), default `10m`, `0` = infinite |
| `?unmute <member\|selector> [reason]` | Remove the `Muted` role |
| `?purge [amount] [user]` | Delete messages (omit amount to delete available messages in chunks), optionally by user |
| `?clear [amount] [user]` | Alias for `?purge` |
| `?purgechannel [channel]` | Delete and recreate a channel with the same properties |
| `?avatar [user]` | Show a user's avatar |
| `?servericon` | Show the server icon |
| `?membercount` | Show the server member count |
| `?userinfo [user]` | Show user account and server details |
| `?serverinfo` | Show server details |

### Entertainment

| Command | What it does |
| --- | --- |
| `/fun 8ball` | Ask the magic 8-ball |
| `/fun coinflip` | Flip a coin |
| `/fun roll` | Roll dice with `1d6`, `2d20`, `3d8+2`, etc. |
| `/fun choose` | Pick one of your comma-separated options |
| `/fun rps` | Play rock, paper, scissors |
| `/fun ship` | Deterministic compatibility score for two users |
| `/fun iq` | Scientifically questionable IQ test |
| `/fun joke` | Random clean joke |
| `/fun truth` | Random truth question |
| `/fun dare` | Random dare |
| `/fun trivia` | Interactive 30-second trivia with buttons |
| `/fun poll` | Button poll with live counts and vote toggling |

### Reactions

| Command | What it does |
| --- | --- |
| `/reaction kiss` | Kiss someone |
| `/reaction cuddle` | Cuddle someone |
| `/reaction punch` | Punch someone |
| `/reaction shoot` | Fire a playful finger gun |
| `/reaction hug` | Hug someone |
| `/reaction slap` | Slap someone |
| `/reaction pat` | Pat someone on the head |
| `/reaction highfive` | High-five someone |
| `/reaction bite` | Playfully bite someone |
| `/reaction boop` | Boop someone's nose |

Each reaction tracks a per-action counter for the user pair and includes response buttons (command-named actions, e.g. “kiss back” / “slap”) so the target can quickly respond.

### Social

| Command | What it does |
| --- | --- |
| `/social marry` | Send a marriage proposal with Accept/Decline buttons |
| `/social divorce` | End your current marriage |
| `/social status` | Show whether a user is married |

### Rate

| Command | What it does |
| --- | --- |
| `/rate rizz` | Rate a user's rizz (0–100%) |
| `/rate aura` | Rate a user's aura (0–100%) |
| `/rate skill` | Rate a user's skill (0–100%) |
| `/rate ragequit` | Rate a user's ragequit energy (0–100%) |

### Utility

| Command | What it does |
| --- | --- |
| `/utility help` | List command groups or inspect one group |
| `/utility ping` | Gateway and database latency |
| `/utility userinfo` | User account and member details |
| `/utility serverinfo` | Server stats |
| `/utility avatar` | User avatar with format links |
| `/utility banner` | User profile banner |
| `/utility botinfo` | Bot stats and uptime |
| `/utility invite` | Guild-install and user-install links |

### Economy

Economy data is **global per user**, shared across servers and DMs.

| Command | What it does |
| --- | --- |
| `/economy balance` | Show a wallet |
| `/economy daily` | Collect daily coins every 24 hours |
| `/economy work` | Earn coins every hour |
| `/economy gamble` | Bet coins for a chance to double or quadruple them |
| `/economy heist` | High-risk 15-minute heist |
| `/economy pay` | Send coins to another user |
| `/economy leaderboard` | Top 10 richest users |

### Levels

XP is **global per user**. Users earn 15–25 XP per message with a 60-second cooldown, and level-up announcements are sent in the channel where the message was sent.

| Command | What it does |
| --- | --- |
| `/level rank` | Show level, XP progress, and leaderboard position |
| `/level leaderboard` | Top 10 XP earners |

### Configuration (server only)

| Command | What it does |
| --- | --- |
| `/config modlog [channel]` | Set the moderation log channel, or omit the channel to disable |
| `/config welcome [channel] [message]` | Enable welcome messages, or omit the channel to disable |
| `/config autorole [role]` | Give new members a role, or omit the role to disable |
| `/config settings` | Show the current configuration |

Welcome message placeholders: `{user}`, `{name}`, `{server}`, `{member_count}`.

---

## Setup

**Requirements:** Python 3.10 or newer and a Discord application.

### 1. Create the application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and give it a name.
3. Open the **Bot** tab and click **Reset Token**.
4. In this project folder, copy `.env.example` to `.env`, then paste the token:

```powershell
Copy-Item .env.example .env
```

```env
DISCORD_TOKEN=your-real-token-here
```

Never commit `.env`.

### 2. Enable the required intents

In **Bot → Privileged Gateway Intents**, enable:

- **Server Members Intent** — required for welcome messages, autorole, and member lookups.
- **Message Content Intent** — required for classic prefix commands such as `?ban`.

XP tracking does not read message content, but the bot is configured with the intent enabled so prefix commands work. Slash commands themselves do not use message content.

### 3. Enable installation types

In **Installation**:

- Enable **Guild Install** if you want moderation, configuration, welcome messages, autorole, and server leveling.
- Enable **User Install** if you want the bot available in DMs.
- Under **Install Link**, choose **Discord Provided Link** (or use the links below).

For Guild Install, use the `bot` and `applications.commands` scopes. For User Install, use only `applications.commands`.

### 4. Invite / install the bot

Replace `YOUR_APP_ID` with the application ID from the **General Information** page.

**Add to a server:**

```text
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&permissions=1099914374230&scope=bot%20applications.commands
```

**Install for your account (DMs):**

```text
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&integration_type=1&scope=applications.commands
```

You can also use `/utility invite` after the bot is online to get both links.

The recommended server permissions integer includes:

- View Channels, Send Messages, Embed Links, Read Message History, Add Reactions
- Manage Messages, Manage Channels, Manage Roles, Manage Nicknames
- Kick Members, Ban Members, Moderate Members

### 5. Install dependencies and run

From this folder:

```powershell
python -m pip install -r requirements.txt
python main.py
```

The token belongs in `GeneralBot/.env`, not in `main.py`.

On first startup the bot creates `data/generalbot.db` and globally syncs its slash commands.

If commands do not appear immediately, refresh Discord with `Ctrl+R`. Global command updates usually appear within a few minutes, but can take longer to propagate.

---

## DM vs. server support

| Group | DMs | Servers |
| --- | --- | --- |
| `/fun` | Yes | Yes |
| `/reaction` | Yes | Yes |
| `/social` | Yes | Yes |
| `/rate` | Yes | Yes |
| `/utility` | Yes | Yes |
| `/economy` | Yes | Yes |
| `/level` | Yes | Yes |
| `/moderation` | Shows a "server only" message | Yes |
| `/config` | Shows a "server only" message | Yes |
| Prefix moderation/roles/server utility | `?help`, `?avatar`, and `?userinfo` work in DMs; the rest show a "server only" message | Yes |
| `?help` | Yes | Yes |

A **user install** is enough for DM commands. For moderation, configuration, welcome messages, autorole, and XP from server messages, add the bot to the server with a guild install.

---

## How the grouped commands are built

Each top-level group is a `commands.GroupCog` class in `generalbot/cogs/`:

```python
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Moderation(commands.GroupCog, group_name="moderation", group_description="..."):
    def __init__(self, bot: GeneralBot) -> None:
        self.bot = bot

    @app_commands.command(name="ban", description="Ban a user from the server")
    async def ban(self, interaction: discord.Interaction, user: discord.User) -> None:
        ...
```

That class produces `/moderation ban`. To add another command, add another `@app_commands.command` method to the class, or create another `GroupCog` and load it in `generalbot/bot.py`.

### Project layout

```text
GeneralBot/
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── data/                       # created at runtime
│   └── generalbot.db
└── generalbot/
    ├── bot.py                  # client, sync, global error handler
    ├── database.py             # async SQLite layer
    ├── helpers.py              # embeds, checks, parsers, formatting
    ├── data.py                 # jokes, truths, dares, trivia, 8-ball answers
    ├── views.py                # trivia, poll, and proposal button views
    └── cogs/
        ├── moderation.py
        ├── prefix.py           # ?ban, .kick, 'timeout, ?role, ?mute, ...
        ├── fun.py
        ├── reaction.py
        ├── social.py
        ├── rate.py
        ├── utility.py
        ├── economy.py
        ├── levels.py
        └── config.py
```

### Storage

- SQLite database: `data/generalbot.db`
- Warnings are stored per server and user.
- Marriages are global per user.
- Reaction counts are stored per action and user pair (shared for both directions).
- Economy balances are global per user.
- XP and levels are global per user.
- Guild configuration is stored per server.

---

## Notes

- Slash commands are synced globally because user-installed apps need global commands for DM use.
- Prefix commands use `?`, `.`, `'`, `;`, or `!` and require Message Content Intent.
- Moderation commands respect role hierarchy and the server owner.
- The bot needs its role moved above roles it should manage (autorole, nickname, kick, ban, timeout).
- Economy and level data are intentionally global so they keep working in DMs.
- Polls, trivia, and pending marriage proposals are in-memory; active views end when the bot restarts.
- Scheduled `?mute` unmutes and `?tempban` unbans are stored in SQLite and processed periodically, so they persist across bot restarts.
- No external APIs or databases are required.
