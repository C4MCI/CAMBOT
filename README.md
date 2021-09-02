# CAMBOT
Hi! Welcome to the official repository of CAMBOT.

## What is CAMBOT?
CAMBOT is a Discord bot specialized for Turkish Discord Community. Most of the commands (except music commands) are in Turkish language.
You can do plenty of things from playing music to reviewing the economical status of Turkey using CAMBOT.

## How To Use?
You can download the files and host the bot yourself by double clicking the launcher.py. But you should create a file named ".env" first. You will need a Discord bot token, sporify client id and client secret, genius access token and a youtube api key. Open the .env file with notepad and add your tokens. Your .env file should look like this:  

TOKEN="YOUR_DISCORD_TOKEN_HERE"  
SPOTIPY_CLIENT_ID="YOUR_SPOTIFY_CLIENT_ID_HERE"  
SPOTIPY_CLIENT_SECRET="YOUR_SPOTIFY_CLIENT_SECRET_HERE"  
GENIUS_ACCESS_TOKEN="YOUR_GENIUS_ACCES_TOKEN_HERE"  
YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY_HERE"  

If you don't want to deal with all of this stuff, you can always add CAMBOT to your server by clicking [this link](https://discord.com/api/oauth2/authorize?client_id=788455398872973342&permissions=8&scope=bot). I am doing my best to keep CAMBOT online all the time but it seems impossible without paying for host. But I will take care of it sometime so just enjoy.

## COMMANDS
This is going to be a long session that I explain all commands of CAMBOT. You might consider skipping that part.

### Music Commands
- ***connect*** (aliases = [join]) --> Connects to the voice channel that you are connected to and does nothing.  
- ***disconnect*** (aliases = [dc, leave, l]) --> Disconnects from the voice channel.  
- ***pause*** (aliases = [wait]) --> Pauses the current track.  
- ***resume*** (no aliases) --> Resumes the current track.  
- ***play*** (alises = [p]) --> Plays a song from the given text, Youtube link, or Spotify link. When you search a song by giving a text for search (example usage: ***.play reloading my mind***), CAMBOT shows 5 results for you to choose from. You can easily choose your song by clicking the reactions that CAMBOT adds. You can also use the play command instead of the resume command for resuming the current track. You can also play Spotify or Youtube playlists using the play command. Of course, you do not need to choose songs if you play a playlist. CAMBOT will create a queue that you can easily jump into songs or shuffle them. We will see when we get to these commands.
- ***queue*** (aliases = [q]) --> Shows the playing queue. You can navigate forward and backward in the queue by clicking the reactions that CAMBOT adds.
- ***stop*** (no  aliases) --> Clears the queue and stops playing.
- ***next*** (aliases = [skip]) --> Skips to the next track in the queue. Keeps playing if there is no track in the queue.
- ***previous*** (aliases = [back]) --> Plays the previous song in the queue.
- ***shuffle*** (no aliases) --> Shuffles the upcoming tracks. Does not shuffle the previous ones.
- ***repeat*** (aliases = [loop]) --> There are 2 repeat modes. These are called "1" and "all". If you use the "1" mode (example usage: ***.repeat 1***) it loops only the current playing song. If you use "all" mode (example usage: ***.repeat all*** or ***.repeat***) it will loop the queue. If you don't specify the repeat mode it will work on "all" mode.
- ***autoplay*** (aliases = [ap, auto]) --> There are 3 situations while using the autoplay command. If you use it barely while CAMBOT is not connected to the voice channel or not playing a song (example usage: ***.autoplay***), it will start to play completely random songs from different genres. If you use it by giving it a genre (example usage: ***.play turkish pop***) it will play random songs from the given genre. If you use it while playing a song, it will play similar songs to the current playing song after the current song.
- ***jump*** (aliases = [skipto]) --> Jumps to the song in the queue by the given number (example usage: ***.jump 6***). You can see the numbers of songs using the queue command.
- ***playnext*** (aliases = [playnext]) --> Works similarly to the play command. The only difference is, chosen song or given playlist using playnext command, queues directly to the next song of the queue.
- ***lyrics*** (no aliases) --> If you use this command while playing a song (example usage: ***.lyrics***), it will show the lyrics of the current playing song. If you use it by giving song name and artist name (example usage: ***.lyrics blank space, taylor swift***), CAMBOT will search for the given song and show the lyrics of it. You can also use it by just giving the name of the song. Just don't forget to use a comma after the song name (example usage: ***.lyrics blank space,***). This command uses Genius.com API.

### Fun Commands
If you are not Turkish, you probably won't understand these jokes about economics in Turkey. So don't mind.
- ***kedi*** (no aliases) --> Posts a random cat photo.
- ***dolar*** (no aliases) --> Shows the USD/TRY exchange rate.
- ***euro*** (no aliases) --> Shows the EUR/TRY exhange rate.
- ***altın*** (no aliases --> Shows the price of 1 gr gold in Turkish Lira.
- ***akp*** (no aliases) --> Shows the improvement of Turkey in the last 20 years XD.
- ***2023*** (no aliases) --> Shows Turkey's enormously extreme and gigantically big power in the year 2023.

### Personal Commands
These are the commands that I use with my friends. There are some inside jokes with these commands so don't mind if you don't understand.
- ***melihtürkçe*** (aliases = [mt]) --> Plays the Melih Civan's special Turkish playlist.
- ***semihtürkçe*** (aliases = [st]) --> Plays the Semih Vicir's special Turkish playlist.
- ***furkansavar*** (no aliases) --> This command will only work if Furkan Toprak is online. Only use this command if you want to enrage Furkan Toprak.
- ***tft*** (no aliases) --> This command will call specific people to come to play Teamfight Tactics.

## Contact
If you find any bugs or if you have any command requests, you can always contact me via [my Twitter account](https://twitter.com/C4MCI). Feel free to ask anything.

## Credits
Basic structure of this bot made by following [Carberra Tutorials's](https://www.youtube.com/channel/UC13cYu7lec-oOcqQf5L-brg) videos. You might want to take a look at his channel if you are interested in coding.  
I used [ZipBomb's repository](https://github.com/ZipBomb/spotify-song-suggestion) to get random songs by genre using Spotify API.  

---
**Project licensed under the MIT License.**
