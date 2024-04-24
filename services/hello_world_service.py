import random
import string
from time import sleep

from oscpy.client import OSCClient
from oscpy.server import OSCThreadServer as OSCServer


def get_lyrics():
    # Create a list to hold the words
    words = []

    # Generate 256 random words
    for _ in range(256):
        # Randomly decide the length of the word (between 4 and 7)
        word_length = random.randint(4, 7)
        # Generate a word of that length using random letters
        word = "".join(
            random.choice(string.ascii_lowercase) for _ in range(word_length)
        )
        words.append(word)

    # Join all the words into a single string separated by spaces
    lyrics = " ".join(words)
    return lyrics


def play_music(music):
    print("play_music", music)

    lyrics = get_lyrics()
    words = lyrics.split(" ")

    for i in range(100):
        sleep(1)
        words_to_send = " ".join(words[i : i + 10])
        music_client.send_message("/music-position", [i])
        music_client.send_message("/music-lyrics", [words_to_send])


music_server = OSCServer(encoding="utf8")
music_server.listen(address=b"localhost", port=3005, default=True)

music_client = OSCClient(b"localhost", 3000, encoding="utf8")

# Now let's create channels to receive messages
music_server.bind(b"/play-music", play_music)


while True:
    # Your service logic here
    print("Hello World!")
    sleep(1)
