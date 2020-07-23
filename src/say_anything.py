#!/usr/bin/python3
# vim: ts=4 expandtab

from __future__ import annotations
from typing import Dict, List, Optional, Sequence, Tuple, Union

import random

import discord

Player = Union[discord.User, discord.Member]


class Game:
    channel: discord.TextChannel
    players: List[Player]
    scores: Dict[Player, int]

    setter_index: int = -1

    # Which user gave the question
    question_setter: Optional[Player] = None

    # What the question was
    question: Optional[str] = None

    # The answers each user over than the question setter gave
    answers: Dict[Player, str] = dict()

    # Temp list of answers in a random order used for the Question
    # Setter to select which is the correct answer
    answer_selection_list: Optional[List[Tuple[Player, str]]] = None

    # Which user gave the correct answer
    correct_answer: Optional[Player] = None

    # Map from mesage to vote on => who gave the answer
    vote_messages: Dict[discord.Message, Player] = dict()

    # A count of how many vote points each user has spent
    votes: Dict[Player, int] = dict()

    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self.players = list()
        self.scores = dict()

    async def add_players(self, players: Sequence[Player]) -> None:
        mentions: List[str] = []

        for player in players:
            if player in self.players:
                continue

            print(f"Adding player {player.name}")
            self.players.append(player)
            self.scores[player] = 0
            mentions.append(player.mention)

        await self.channel.send(", ".join(mentions) + " have been added to the game")

        if not self.question_setter and len(self.players) >= 2:
            print("Starting first round")
            await self.start_round()

    async def start_round(self) -> None:
        if self.question_setter:
            return

        self.setter_index += 1

        if self.setter_index >= len(self.players):
            self.setter_index = 0

        self.question_setter = self.players[self.setter_index]
        self.question = None
        self.answers = dict()
        self.correct_answer = None
        self.answer_selection_list = None
        self.vote_messages = dict()
        self.votes = dict()

        await self.channel.send(
            (
                f"{self.question_setter.mention}, please set your question! e.g.\n"
                "!question What would be a perfect vacation?"
            )
        )

    async def request_answers(self) -> None:
        setter = self.question_setter

        if setter is None:
            return

        message = (
            f"What answer do you think {setter.name}"
            f" would give to '{self.question}'?"
        )

        for player in self.players:
            if player == self.question_setter:
                continue

            print(f"Messaging {player.name} for an answer")
            await player.send(message)

    async def request_answer_selection(self) -> None:
        setter = self.question_setter

        if setter is None:
            return

        self.answer_selection_list = [(k, v) for k, v in self.answers.items()]
        random.shuffle(self.answer_selection_list)

        text = f"Select the answer for {self.question} that is most 'you'\n\n"

        for idx, (_, answer) in enumerate(self.answer_selection_list, start=1):
            text += f"{idx} - {answer}\n\n"

        text += f"Please respond with a number between 1 and {len(self.answer_selection_list)}"

        print(f"Messaging question setter {setter.name} to select an answer")
        await setter.send(text)

    async def select_answer(self, index: int) -> None:
        if index < 1:
            return

        selection_list = self.answer_selection_list or []

        if index > len(selection_list):
            return

        print(f"Selecting answer {index}")
        self.correct_answer = selection_list[index - 1][0]
        print(f"This answer was given by {self.correct_answer.name}")
        self.answer_selection_list = None

        answers: List[Tuple[Player, str]] = [(k, v) for k, v in self.answers.items()]
        random.shuffle(answers)

        for idx, (user, answer) in enumerate(answers, start=1):
            message = await self.channel.send(f'[{idx}]: "{answer}"')

            self.votes[user] = 0
            self.vote_messages[message] = user

            await message.add_reaction("1️⃣")
            await message.add_reaction("2️⃣")

    async def handle_reaction(self, event: discord.RawReactionActionEvent) -> None:
        player = event.member

        if self.correct_answer is None:
            return

        if event.emoji.name not in ["1️⃣", "2️⃣"]:
            print(f"Got incorrect emote: {event.emoji.name}")
            return

        if not player or player not in self.votes:
            print(
                f"Got emote from non-player {player.name if player else 'unknown user'}"
            )
            return

        message = next(
            (
                message
                for message in self.vote_messages
                if message.id == event.message_id
            )
        )

        if not message:
            print("Got emote from not on a vote message")
            return

        vote_for = self.vote_messages[message]
        print(f"{player.name} votes for {vote_for.name}'s answer")

        if event.emoji.name == "2️⃣":
            self.votes[player] += 2
        else:
            self.votes[player] += 1

        for voter in self.votes:
            if self.votes[voter] < 2:
                print(f"Player {voter.name} has not finished voting")
                return

        print("All players have voted")

        await self.channel.send(
            (
                f"The correct answer was {self.answers[self.correct_answer]}\n"
                f"This answer was given by {self.correct_answer.name}"
            )
        )

        self.question_setter = None
        await self.channel.send(
            (
                "Scoring is not yet implemented.\n"
                "Use !nextround to start the next round, or !endgame to stop"
            )
        )

    async def handle_channel_message(self, message: discord.Message) -> None:
        if message.content.startswith("!nextround"):
            await self.start_round()
            return

        if message.content.startswith("!addplayers "):
            await self.add_players(message.mentions)
            return

        if message.content.startswith("!question "):
            if self.question:
                print("Skipping !question because we have a question")
                return

            if message.author != self.question_setter:
                print("Skipping !question because not from the setter")
                return

            self.question = message.content[10:].strip()
            print("Question has been set")
            await self.request_answers()

            return

    async def handle_player_message(self, message: discord.Message) -> None:
        # No user operations are available when there is no question
        # (the question is posted into the channel).
        if not self.question:
            print(
                "Received message form {message.author.name} when there is no question"
            )
            return

        # The question setter should only message us
        # when they are selecting an answer
        if message.author == self.question_setter:
            if not self.answer_selection_list:
                print("Question Setter trying to select answer at wrong time?")
                return

            if message.content.isnumeric():
                print("Selected answer: " + message.content)
                await self.select_answer(int(message.content))

            return

        # Once the question setting is selecting an answer, we don't
        # accept any more answers.
        if self.answer_selection_list or self.correct_answer:
            print(
                f"Received answer from {message.author.name} when one has already been selected"
            )
            return

        # Otherwise, accept this answer.
        self.answers[message.author] = message.content.strip()

        await message.add_reaction("\U0001F44D")
        print(f"Accepted answer from {message.author.name}")

        print(f"We have {len(self.answers)} and {len(self.players)}")
        if len(self.answers) == len(self.players) - 1:
            print("Requesting answer selection")
            await self.request_answer_selection()


class DiscordBot(discord.Client):
    games: List[Game] = []

    async def on_ready(self) -> None:
        print(f"{self.user} has connected to Discord!")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        if message.content.startswith("!startgame "):
            self.start_game(message)
            return

        if message.content.startswith("!endgame"):
            for game in self.games:
                if message.channel == game.channel:
                    self.games.remove(game)
                    await game.channel.send("Thanks for Playing!")
                    return

        for game in [game for game in self.games if message.channel == game.channel]:
            await game.handle_channel_message(message)
            return

        if isinstance(message.channel, discord.DMChannel):
            user = message.channel.recipient

            for game in [game for game in self.games if user in game.players]:
                await game.handle_player_message(message)
                return

    async def on_raw_reaction_add(self, event: discord.RawReactionActionEvent) -> None:
        if event.user_id == self.user.id:
            return

        for game in self.games:
            if event.channel_id == game.channel.id:
                await game.handle_reaction(event)

                return

    async def start_game(self, message: discord.Message) -> None:
        if not isinstance(message.channel, discord.TextChannel):
            print("Attempting to start game in non-text channel")
            return

        for game in self.games:
            if message.channel == game.channel:
                await game.channel.send("Can't start game -- game already exists")
                return

        game = Game(message.channel)
        self.games.append(game)

        print(f"Starting new game in {message.channel.name} with {message.mentions}")

        await game.add_players(message.mentions)


if __name__ == "__main__":
    with open("discord.token", "r") as token_handle:
        token = token_handle.read().strip()

    bot = DiscordBot(max_messages=4096)
    bot.run(token)
