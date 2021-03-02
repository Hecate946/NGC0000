import discord
import logging
import datetime

from discord.ext import commands

from utilities import default, permissions
from core import OWNERS
from collections import OrderedDict, Counter


def setup(bot):
    if not hasattr(bot, 'command_stats'):
        bot.command_stats = Counter()

    if not hasattr(bot, 'socket_stats'):
        bot.socket_stats = Counter()

    bot.add_cog(Statistics(bot))

#log = logging.getLogger()

class Statistics(commands.Cog):
    """
    Statistics on users, activity, and more.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cxn = bot.connection


    async def fix_member(self, member):
        roles = ','.join([str(x.id)
                                for x in member.roles if x.name != "@everyone"])
        names = member.display_name
        query = '''INSERT OR IGNORE INTO users VALUES ($1, $2, $3, $4, $5, $6, $7, $8)'''
        await self.cxn.execute(query, roles, str(member.guild.id), None, member.id, names, 0, 0, 0)      
    

    @commands.command(aliases=['listinvites','invitelist'], pass_context=True, brief="List all current server invites.")
    @commands.guild_only()
    @permissions.has_permissions(manage_invites=True)
    async def invites(self, ctx):
        """
        Usage: -invites
        Aliases: -listinvites -invitelist
        Output: Embed with all server invites listed
        Permission: Manage Messages
        """
        invites = await ctx.guild.invites()
        if len(invites) == 0:
            await ctx.send("`:warning: There currently no invites active.`")
        else:
            try:
                em = discord.Embed(description="**Invites:**\n {0}".format(",\n ".join(map(str, invites))), color=ctx.guild.me.color)
                await ctx.send(embed=em)
            except: return await ctx.send(f"<:fail:812062765028081674> Too many invites to list.")


    @commands.command(aliases=['mc'], brief="Find exactly how many messages a user has sent in the server.")
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def messagecount(self, ctx, member: discord.Member = None):
        """
        Usage:  -messagecount [user]
        Alias:  -mc
        Output: Shows how many messages a user has sent on the server.
        Permission: Manage Messages
        Notes:
            Will default to yourself if no user is passed.
        """
        user = ctx.author if member is None else member
        query = '''SELECT messagecount FROM users WHERE id = $1 AND server_id = $2'''
        a = await self.cxn.fetchrow(query, user.id, ctx.guild.id) or (None)
        if a is None:
            #await self.fix_member(ctx.author)
            return await ctx.send("`{}` has sent **0** messages.".format(user))
        else:
            a = int(a[0])
            await ctx.send(f"`{user}` has sent **{a}** message{'' if a == 1 else 's'}")


    @commands.command(brief="Show the top message senders in the server", pass_context=True)
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def top(self, ctx):
        """
        Usage: -top
        Output: Top message senders in the server
        Permission: Manage Messages
        """
        query = '''SELECT * FROM users WHERE (server_id = $1 AND messagecount > 0) ORDER BY messagecount DESC LIMIT 20'''
        a = await self.cxn.fetch(query, ctx.guild.id)
        sum_query = '''SELECT SUM(messagecount) FROM users WHERE (server_id = $1 AND messagecount > 0)'''
        b = await self.cxn.fetchrow(sum_query, ctx.guild.id)
        b = b[0]
        post_this = ""
        rank = 1
        for row in a:
            name = f'<@{row[0]}>'
            post_this += ("{}. {} (Messages: {})\n".format(rank, name, row[4]))
            rank += 1
        post_this += "\n**{0}** messages by **{1}** users.".format(
            b, len([x for x in ctx.guild.members]))
        em = discord.Embed(
                           description=post_this, colour=default.config()["embed_color"])
        em.set_author(name=self.bot.user.name,
                      icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=em)


    @commands.command(brief="Show all past and current nicknames for a user on the server.", aliases=["nicknames"])
    @commands.guild_only()
    async def nicks(self, ctx, user: discord.Member = None):
        """
        Usage: -nicks [user]
        Alias: -nicknames
        Output: Embed of all user's nicknames.
        Permission: Manage Messages
        Notes:
            Will default to yourself if no user is passed
        """
        if user is None:
            user = ctx.author
        query = '''SELECT nicknames FROM users WHERE server_id = $1 AND id = $2'''
        name_list = await self.cxn.fetchrow(query, ctx.guild.id, user.id)
        name_list = name_list[0].split(',')
        name_list = name_list[-10:]
        name_list = list(OrderedDict.fromkeys(name_list))
        msg = ""
        integer = 0
        for i in name_list:
            integer += 1
            msg += f"{str(integer).zfill(2)}. `{i}`\n"
        
        embed = discord.Embed(color=default.config()["embed_color"])
        embed.description = msg
        embed.set_author(name=f"{user.name}'s Nicknames")
        await ctx.send(embed=embed)


    @commands.command(brief="👀 Check a user's eyecount 👀", aliases=['👀','eyecount'])
    @commands.guild_only()
    async def eyes(self, ctx, user: discord.Member = None):
        """
        Usage:   -eyes [user]
        Aliases: -eyecount 👀
        Output:  👀 Check a user's eyecount 👀
        Notes:
            Will default to yourself if no user is passed
        """
        if user is None:
            user = ctx.author
        query = '''SELECT eyecount FROM users WHERE id = $1 AND server_id = $2'''
        eyes = await self.cxn.fetchrow(query, ctx.author.id, ctx.guild.id)
        await ctx.send(f"👀 User `{user}` has sent {eyes[0]} 👀 emoji{'' if int(eyes[0]) == 1 else 's'}")


    @commands.command(brief="Get how long ago a user was seen by the bot.", aliases=['seen'], hidden=True)
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def lastseen(self, ctx, *, user: discord.User):
        """
        Usage:  -lastseen [user]
        Alias:  -seen
        Output: Get when a user was last seen on discord.
        Permission: Manage Messages
        Notes:
            User can be a mention, user id, or full discord 
            username with discrim Username#0001.
            Will default to yourself if no user is passed
        """
        query = '''SELECT timestamp FROM last_seen WHERE id = $1;'''
        timestamp = await self.cxn.fetchrow(query, user.id) or (None)
        if str(timestamp) == "None": return await ctx.send(f"I have not seen `{user}`")
        timestamp = timestamp[0]
        everything = []
        first_time = timestamp
        later_time = datetime.datetime.utcnow()
        difference = later_time - first_time
        seconds_in_day = 24 * 60 * 60
        elapsed = divmod(difference.days * seconds_in_day + difference.seconds, 60)
        args = str(elapsed).strip("()").replace(",","").split(" ")
        seconds = args[1]
        everything.append(str(seconds) + " seconds")
        if int(args[0]) > 60:
            elapsed2 = divmod(int(args[0]), 60)
            args2 = str(elapsed2).strip("()").replace(",","").split(" ")
            minutes = args2[1]
            everything.append(str(minutes) + f" minute{'' if int(minutes) == 1 else 's'}")
            if int(args2[0]) > 24:
                elapsed3 = divmod(int(args2[0]), 24)
                args3 = str(elapsed3).strip("()").replace(",","").split(" ")
                hours = args3[1]
                everything.append(str(hours) + f" hour{'' if int(hours) == 1 else 's'}")
                if int(args3[0]) > 30:
                    elapsed4 = divmod(int(args2[0]), 30)
                    args4 = str(elapsed4).strip("()").replace(",","").split(" ")
                    days = args4[1]
                    everything.append(str(days) + f" day{'' if int(days) == 1 else 's'}")
                    if int(args4[0]) > 12:
                        elapsed5 = divmod(int(args2[0]), 12)
                        args5 = str(elapsed5).strip("()").replace(",","").split(" ")
                        months = args5[1]
                        years = args5[0]
                        everything.append(str(months) + f" month{'' if int(months) == 1 else 's'}")
                        everything.append(str(years) + f" year{'' if int(years) == 1 else 's'}")
                    else:
                        months = args4[0]
                        everything.append(str(months) + f" month{'' if int(months) == 1 else 's'}")
                else:
                    days = args3[0]
                    everything.append(str(days) + f" day{'' if int(days) == 1 else 's'}")
            else:
                hours = args2[0]
                everything.append(str(hours) + f" hour{'' if int(hours) == 1 else 's'}")
        else:
            minutes = args[0]
            everything.append(str(minutes) + f" minute{'' if int(minutes) == 1 else 's'}")
        everything.reverse()
        everything = str(everything).strip("[]").replace("'","")
        msg = f"User: `{user}` was last seen **{everything}** ago"
        await ctx.send(msg)


    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def cachedcommands(self, ctx, limit=20):
        counter = self.bot.command_stats
        width = len(max(counter, key=len))
        total = sum(counter.values())

        if limit > 0:
            common = counter.most_common(limit)
        else:
            common = counter.most_common()[limit:]
        output = '\n'.join('{0:<{1}} : {2}'.format(k, width, c)
                           for k, c in common)

        await ctx.send('```yaml\n{}\n```'.format(output))


    @commands.command(brief="Show bot commands listed by popularity")
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def commandstats(self, ctx, user: discord.Member = None, limit=25):
        """
        Usage: -commandstats [user] [limit]
        Output: Most popular commands
        Permission: Manage Messages
        """
        if user is None:
            query = '''SELECT command FROM commands WHERE server_id = $1'''
            command_list = await self.cxn.fetch(query, ctx.guild.id)
            premsg = f"Commands most frequently used in **{ctx.guild.name}**"
        else:
            query = '''SELECT command FROM commands WHERE server_id = $1 AND executor_id = $2'''
            command_list = await self.cxn.fetch(query, ctx.guild.id, user.id)
            premsg = f"Commands most frequently used by **{user}**"
        formatted_list = []
        for c in command_list:
            formatted_list.append(c[0])

        counter = Counter(formatted_list)
        try:
            width = len(max(counter, key=len))
        except ValueError: return await ctx.send(f":warning: User `{user}` has not run any commands.")
        total = sum(counter.values())

        if limit > 0:
            common = counter.most_common(limit)
        else:
            common = counter.most_common()[limit:]
        output = '\n'.join('{0:<{1}} : {2}'.format(str(k), width, c)
                           for k, c in common)

        await ctx.send(premsg + '```yaml\n{}\n\nTOTAL: {}```'.format(output, total))


    @commands.command(brief="Global socketstats", hidden=True)
    @commands.is_owner()
    async def socketstats(self, ctx, limit=20):
        """
        Usage: -socketstats [limit]
        Output: Global bot socketstats
        Permission: Bot Owner
        """
        delta = datetime.datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        width = len(max(self.bot.socket_stats, key=lambda x: len(str(x))))
        con = self.bot.socket_stats.most_common(limit)
        fancy = '\n'.join('{0:<{1}} : {2:>12,}'.format(str(k), width, c) for k, c in con)

        await ctx.send('{0:,} socket events observed ({1:.2f}/minute):\n```yaml\n{2}```'.format(total, cpm, fancy))


    @commands.command(name="commands", brief="Show how many commands have been executed on the server.")
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def command_count(self, ctx, user: discord.Member = None):
        '''
        Usage:  -commands [user]
        Output: Command count
        Permission: Manage Messages
        Notes:
            If no user is passed, will show total server commands
        '''
        if user is None:
            query = '''SELECT COUNT(*) as c FROM commands WHERE server_id = $1'''
            command_count = await self.cxn.fetchrow(query, ctx.guild.id)
            return await ctx.send(f"A total of **{command_count[0]:,}** command{' has' if int(command_count[0]) == 1 else 's have'} been executed on this server.")
        else:
            query = '''SELECT COUNT(*) as c FROM commands WHERE executor_id = $1 AND server_id = $2'''
            command_count = await self.cxn.fetchrow(query, user.id, ctx.guild.id)
            return await ctx.send(f"User `{user}` has executed **{int(command_count[0]):,}** commands.")


    @commands.command(brief="See the top bot users in the server.",aliases=["botusage"])
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def usage(self, ctx, unit: str="month"):
        """
        Usage: -usage [unit of time]
        ALias: -botusage
        Output: Top bot users in the server
        Permission: Manage Messages
        """
        unit = unit.lower()
        time_dict = {
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31556952
        }
        if unit not in time_dict:
            unit = "month"
        query = '''SELECT COUNT(*) as c, executor FROM commands WHERE server_id = $1 GROUP BY executor ORDER BY c DESC LIMIT 25'''
        usage = await self.cxn.fetch(query, ctx.guild.id)
        e = discord.Embed(title=f"Activity for the last {unit}", description=f"{sum(x[0] for x in usage)} commands from {len(usage)} user{'' if len(usage) == 1 else 's'}", color=default.config()["embed_color"])
        for n, v in enumerate(usage[:25]):
            name = v[1]
            e.add_field(name=f"{n+1}. {name}", value=f"{v[0]} command{'' if int(v[0]) == 1 else 's'}")
        
        await ctx.send(embed=e)
        print(n)


    @commands.group(brief="Show the most active server members", invoke_without_command=True)
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def activity(self, ctx, unit: str="month"):
        """
        Usage: -activity [characters] [unit of time]
        Output: Top message senders in the server
        Permission: Manage Messages
        """
        unit = unit.lower()
        time_dict = {
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31556952
        }
        if unit not in time_dict:
            unit = "month"
        time_seconds = time_dict.get(unit, 2592000)
        now = int(datetime.datetime.utcnow().timestamp())
        diff = now - time_seconds
        query = '''SELECT COUNT(*) as c, author FROM messages WHERE server_id = $1 AND unix > $2 GROUP BY author ORDER BY c DESC LIMIT 25'''
        stuff = await self.cxn.fetch(query, ctx.guild.id, diff)

        e = discord.Embed(title=f"Activity for the last {unit}", description=f"{sum(x[0] for x in stuff)} messages from {len(stuff)} user{'' if len(stuff) == 1 else 's'}", color=default.config()["embed_color"])
        for n, v in enumerate(stuff[:25]):
            try:
                name = ctx.guild.get_member(int(v[1])).name
            except AttributeError:
                name = f"Unknown member"
            e.add_field(name=f"{n+1}. {name}", value=f"{v[0]} message{'' if int(v[0]) == 1 else 's'}")
        
        await ctx.send(embed=e)

    @activity.command(aliases=['characters'])
    @commands.guild_only()
    async def char(self, ctx, unit: str="day"):
        if ctx.author.id not in OWNERS and ctx.author.guild_permissions.administrator:
            return
        unit = unit.lower()
        time_dict = {
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31556952
        }
        if unit not in time_dict:
            unit = "month"
        time_seconds = time_dict.get(unit, 2592000)
        now = int(datetime.datetime.utcnow().timestamp())
        diff = now - time_seconds
        query = '''SELECT SUM(LENGTH(content)) as c, author, COUNT(*) FROM messages WHERE server = $1 AND unix > $2 GROUP BY author ORDER BY c DESC LIMIT 25'''
        stuff = await self.cxn.fetch(query, ctx.guild.id, diff)
        e = discord.Embed(title="Current leaderboard", description=f"Activity for the last {unit}", color=default.config()["embed_color"])
        for n, v in enumerate(stuff): 
            try:
                name = ctx.guild.get_member(int(v[1])).name
            except AttributeError:
                name = "Unknown member"
            #ratio = int(v[0] / 1440)
            #e.add_field(name=f"{n+1}. {name}", value=f"{v[0]:,} chars ({ratio} chars/minute)")
            e.add_field(name=f"{n+1}. {name}", value=f"{v[0]:,} chars")
        
        await ctx.send(embed=e)

    @commands.command(brief="Get the most commonly used words of a user.")
    @commands.guild_only()
    @permissions.has_permissions(manage_messages=True)
    async def words(self, ctx, *, member: discord.Member=None):
        """
        Usage: -words [user]
        Output: Most commonly used words by the passed user
        Permission: Manage Messages
        Notes:
            Will default to yourself if no user is passed.
        """
        if member is None:
            member = ctx.author

        all_msgs = await self.cxn.fetch('''SELECT content FROM messages WHERE author = $1 AND server = $2''', member.id, ctx.guild.id)
        all_msgs = [x[0] for x in all_msgs]
        all_msgs = ' '.join(all_msgs).split()
        all_msgs = list(filter(lambda x: len(x) > 3, all_msgs))
        all_words = (Counter(all_msgs).most_common()[:20])
        msg = ""
        integer = 0
        for i in all_words:
            i = str(i).strip("(),'\"").replace("'","").replace('"',"").replace(",","").replace(":","").replace(".","")
            args = i.split(" ")
            integer += 1
            msg += f'[{str(integer).zfill(2)}] Uses: [{args[1].zfill(2)}] Word: {args[0]}\n'
        
        await ctx.send(f"Most common words sent by **{member.display_name}**```ini\n{msg}```")

      #####################
     ## Event Listeners ##
    #####################


    @commands.Cog.listener()
    async def on_command(self, ctx):
        if not ctx.guild: return
        try:
            await self.cxn.execute(
                """ UPDATE users 
                    SET commandcount = commandcount + 1 
                    WHERE id = $1 
                    AND server_id = $2 
                """, ctx.author.id, ctx.guild.id
            )
        except AttributeError:
            return

        query = '''INSERT INTO commands VALUES ($1, $2, $3, $4, $5, $6, $7)'''
        await self.cxn.execute(
            query, 
            ctx.message.created_at.utcnow(), 
            ctx.command.qualified_name, 
            ctx.message.content, 
            str(ctx.author), 
            ctx.author.id,
            ctx.channel.id, 
            ctx.guild.id)

        command = ctx.command.qualified_name
        self.bot.command_stats[command] += 1
    

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return None
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, message.author.id, datetime.datetime.utcnow())
        if not message.guild: return
        
        message_eyes = 0 
        trigger = '👀'
        for x in str(message.content):
            if x == trigger:
                message_eyes += 1
        query = '''UPDATE users SET eyecount = eyecount + $1 WHERE id = $2 AND server_id = $3'''
        await self.cxn.execute(query, message_eyes, message.author.id, message.guild.id)

        query = '''UPDATE users SET messagecount = messagecount + 1 WHERE id = $1 AND server_id = $2'''
        await self.cxn.execute(query, message.author.id, message.guild.id)   

        if message.content == "":
            return
        query = '''INSERT INTO messages VALUES ($1, $2, $3, $4, $5, $6, $7)'''
        await self.cxn.execute(
            query,
            message.created_at.timestamp(), 
            message.created_at.utcnow(), 
            message.clean_content,
            message.id,
            message.author.id,
            message.channel.id,
            message.guild.id)


    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.display_name != after.display_name:
            print("before name is not after name")
            query = '''SELECT nicknames FROM users WHERE id = $1 AND server_id = $2'''
            name_list = await self.cxn.fetchrow(query, before.id, before.guild.id)

            name_list = name_list[0].split(',')
            name_list = list(OrderedDict.fromkeys(name_list))

            if after.display_name not in name_list:
                name_list.append(after.display_name)
            else:

                old_index = name_list.index(after.display_name)
                name_list.pop(old_index)
                name_list.append(after.display_name)
            new_names = ','.join(name_list)
            print(new_names)
            query = '''UPDATE users SET nicknames = $1 WHERE id = $2 AND server_id = $3'''
            await self.cxn.execute(query, new_names, before.id, before.guild.id)


    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        user = await self.bot.fetch_user(payload.user_id)
        await self.cxn.execute(query, user.id, datetime.datetime.utcnow())
    
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, member.id, datetime.datetime.utcnow())
    
    
    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, after.id, datetime.datetime.utcnow())
    
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, invite.inviter.id, datetime.datetime.utcnow())
    
    
    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        await self.bot.wait_until_ready()
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, user.id, datetime.datetime.utcnow())


    @commands.Cog.listener()
    async def on_member_join(self, user):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, user.id, datetime.datetime.utcnow())


    @commands.Cog.listener()
    async def on_member_leave(self, user):
        query = '''INSERT INTO last_seen (id, timestamp) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET timestamp = $2'''
        await self.cxn.execute(query, user.id, datetime.datetime.utcnow())
