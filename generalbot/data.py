"""Static content for GeneralBot's entertainment commands."""

EIGHT_BALL: dict[str, list[str]] = {
    "positive": [
        "It is certain.",
        "Without a doubt.",
        "Absolutely.",
        "You may rely on it.",
        "Most likely.",
        "Outlook good.",
        "Yes, definitely.",
        "Signs point to yes.",
        "The stars have aligned.",
        "Bet on it.",
    ],
    "neutral": [
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "My sources are confused.",
        "The answer is somewhere between yes and no.",
        "Outlook unclear.",
    ],
    "negative": [
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful.",
        "Absolutely not.",
        "The vibes say no.",
        "Not happening.",
        "I wouldn't bet on it.",
    ],
}

JOKES: list[str] = [
    "Why don't programmers like nature? It has too many bugs.",
    "I told my computer I needed a break, and it said: 'No problem, I'll go to sleep.'",
    "Why was the JavaScript developer sad? Because he didn't know how to 'null' his feelings.",
    "There are 10 types of people in the world: those who understand binary, and those who don't.",
    "Why do Java developers wear glasses? Because they don't C#.",
    "A SQL query walks into a bar, sees two tables, and asks: 'Can I join you?'",
    "Why did the developer go broke? Because he used up all his cache.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "What do you call a fake noodle? An impasta.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "I used to hate facial hair, but then it grew on me.",
    "What do you call a bear with no teeth? A gummy bear.",
    "Why did the math book look sad? It had too many problems.",
    "I asked the gym trainer if he could teach me to do the splits. He said, 'How flexible are you?' I said, 'I can't make Tuesdays.'",
    "What do you call a fish wearing a bowtie? Sofishticated.",
    "Why did the coffee file a police report? It got mugged.",
    "I'm on a seafood diet. I see food and I eat it.",
    "Why did the bicycle fall over? It was two-tired.",
]

TRUTHS: list[str] = [
    "What is the most embarrassing song on your playlist?",
    "What is the last lie you told?",
    "Who was your first crush?",
    "What is the weirdest thing you have ever eaten?",
    "What is your most useless talent?",
    "What is the biggest mistake you have made this year?",
    "What is one thing you would change about your past?",
    "What is the most childish thing you still do?",
    "What is a secret you have never told anyone here?",
    "What is the last thing you searched for on the internet?",
    "What is your guilty pleasure?",
    "Who in this chat would you trust with your phone unlocked?",
    "What is the most awkward thing that has happened to you in public?",
    "What is a compliment you have received that you will never forget?",
    "What is one fear you are still trying to get over?",
]

DARES: list[str] = [
    "Send the last emoji you used, with no context.",
    "Type your next message with your elbows.",
    "Change your nickname to something embarrassing for 10 minutes.",
    "Send a selfie with the goofiest face you can make.",
    "Speak only in third person for the next five messages.",
    "Tell the chat a terrible joke.",
    "Send a voice message singing the first song that comes to mind.",
    "Use only capital letters for the next three messages.",
    "Describe your day like a movie trailer.",
    "Post your most-used emoji three times in a row.",
    "Give a sincere compliment to the last person who messaged.",
    "Type a sentence using only emojis and let the chat guess it.",
    "Do your best impression of another person in the chat.",
    "Send a picture of the nearest object to your left.",
    "Rename yourself to 'Definitely Not Sus' for 10 minutes.",
]

TRIVIA: list[dict] = [
    {
        "question": "What is the capital of France?",
        "choices": ["Berlin", "Madrid", "Paris", "Rome"],
        "answer": 2,
    },
    {
        "question": "Which planet is the largest in our solar system?",
        "choices": ["Saturn", "Jupiter", "Neptune", "Earth"],
        "answer": 1,
    },
    {
        "question": "What is the chemical symbol for gold?",
        "choices": ["Ag", "Au", "Gd", "Go"],
        "answer": 1,
    },
    {
        "question": "Which animal is the fastest on land?",
        "choices": ["Lion", "Cheetah", "Horse", "Pronghorn"],
        "answer": 1,
    },
    {
        "question": "How many continents are there on Earth?",
        "choices": ["5", "6", "7", "8"],
        "answer": 2,
    },
    {
        "question": "Who was the first person to walk on the Moon?",
        "choices": ["Buzz Aldrin", "Yuri Gagarin", "Neil Armstrong", "Michael Collins"],
        "answer": 2,
    },
    {
        "question": "What is the largest mammal in the world?",
        "choices": ["African elephant", "Blue whale", "Giraffe", "Orca"],
        "answer": 1,
    },
    {
        "question": "What is the hardest natural substance on Earth?",
        "choices": ["Quartz", "Titanium", "Diamond", "Obsidian"],
        "answer": 2,
    },
    {
        "question": "Which country has the largest population?",
        "choices": ["India", "China", "United States", "Indonesia"],
        "answer": 0,
    },
    {
        "question": "What is the currency of Japan?",
        "choices": ["Won", "Yuan", "Yen", "Ringgit"],
        "answer": 2,
    },
    {
        "question": "How many sides does a hexagon have?",
        "choices": ["5", "6", "7", "8"],
        "answer": 1,
    },
    {
        "question": "In which year did World War II end?",
        "choices": ["1943", "1944", "1945", "1946"],
        "answer": 2,
    },
    {
        "question": "Who painted the Mona Lisa?",
        "choices": ["Vincent van Gogh", "Pablo Picasso", "Leonardo da Vinci", "Michelangelo"],
        "answer": 2,
    },
    {
        "question": "What is the largest desert in the world?",
        "choices": ["Sahara", "Gobi", "Antarctic", "Arabian"],
        "answer": 2,
    },
    {
        "question": "Which gas do plants absorb from the atmosphere?",
        "choices": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"],
        "answer": 2,
    },
    {
        "question": "How many strings does a standard guitar have?",
        "choices": ["4", "5", "6", "7"],
        "answer": 2,
    },
    {
        "question": "What is the smallest prime number?",
        "choices": ["0", "1", "2", "3"],
        "answer": 2,
    },
    {
        "question": "Which ocean is the largest?",
        "choices": ["Atlantic", "Indian", "Arctic", "Pacific"],
        "answer": 3,
    },
    {
        "question": "What is the capital of Australia?",
        "choices": ["Sydney", "Melbourne", "Canberra", "Perth"],
        "answer": 2,
    },
    {
        "question": "What does 'CPU' stand for?",
        "choices": [
            "Central Process Unit",
            "Central Processing Unit",
            "Computer Personal Unit",
            "Central Processor Utility",
        ],
        "answer": 1,
    },
]

JOBS: list[str] = [
    "debugged a Discord bot",
    "sold a slightly used graphics card",
    "fixed the printer by hitting it",
    "wrote documentation nobody will read",
    "survived a meeting that could have been an email",
    "deleted 400 lines of code and felt powerful",
    "explained what 'restarting it' means",
    "found the missing semicolon",
    "tested in production and got away with it",
    "reorganized the server's emoji collection",
    "translated a bug report from all-caps to English",
    "renewed a domain name at the last minute",
]

HEIST_SUCCESS: list[str] = [
    "The vault door swings open. The guards are still arguing about the Wi-Fi password.",
    "You repelled in from the roof, grabbed the loot, and left before the alarm finished booting.",
    "The getaway driver was early. A miracle, honestly.",
    "You swapped the diamonds for a bag of dice. Nobody noticed.",
    "The laser grid was off. You almost feel bad about how easy that was.",
]

HEIST_FAILURE: list[str] = [
    "You tripped the alarm, the lights came on, and everyone saw you wearing a paper bag mask.",
    "The vault was empty except for a sticky note reading 'nice try'.",
    "Your getaway car was a shopping cart. It did not get away.",
    "You spent the whole heist stuck in the ventilation shaft.",
    "The guards were not fooled by your 'totally a technician' badge.",
]
