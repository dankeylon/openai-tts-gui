# -*- coding: utf-8 -*-
"""
Created on Thu Nov  9 16:19:04 2023

@author: Daniel

"""
import math
import time

import joblib as jb

from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI
from pydub import AudioSegment

client = OpenAI()

class Book():
    """Object to store a .txt file in a format amenable to sending
    to the OpenAI TTS api.
    """
    
    disclaimer = "Note: This audio recording was generated using an AI voice provided by OpenAI. \n"
    
    def __init__(self, path_to_book: Path, chunk_size: int = 4096) -> None:
        """Object instantiation.

        Inputs
        path_to_book: A Path object containing the path to a plain
            text file
        chunk_size: An integer specifying how many characters should
            be in each chunk

        """
        
        self.path_to_book = path_to_book
        self.name = path_to_book.stem
        
        with open(self.path_to_book, 'r', errors="ignore") as f:
            book_text = f.readlines()
        
        # Join the disclaimer and all the lines into a single string
        book_text = [self.disclaimer] + book_text
        self.book_text = ' '.join(book_text)

        self.chunks = self.chunk_book(self.book_text, chunk_size)
        
    def chunk_book(self, book_text: str, chunk_size: int) -> list[str]:
        """Create a sequence of appropriately sized text chunks

        OpenAIs TTS api requires requests to contain less than an
        arbitrary number of characters.  This method reportions 
        the book into a list of acceptably sized chunks that 
        don't interrupt sentences.

        Inputs
        book_text: A string containing the entire text of the book
        chunk_size: An integer specifying how many characters each 
            chunk should maximally be

        Outputs
        chunks: A list containing each generated chunk.

        """

        chunks = []
        
        end = 0
        for start in range(0, len(book_text), chunk_size):
            start = end
            
            if start + chunk_size < len(book_text):    
                end = start + chunk_size
                
                idx = 0
                while book_text[end-idx] not in ['.', '?', '!']:
                    idx = idx + 1
                
                end = end - idx + 1
                
            else:
                end = len(book_text) - 1
                
            chunks.append(book_text[start:end])
            
        return chunks

    
class TTS_API_Wrapper():
    """Object that provides ease of use utilities for interfacing with the 
    OpenAI TTS api.  Can be used to create a singular .mp3 file from an 
    arbitrarily sized text file stored in a Book object.
    
    """

    # Usage details from OpenAI website
    max_requests_per_min = 50
    token_size = 1000
    cost_per_token = {"tts-1": 0.015, "tts-1-hd": 0.03}
    
    def __init__(self, 
                book: Book, 
                out_path: Path,
                model: str = "tts-1",
                voice: str = "onyx",
                overwrite_protect: bool = True) -> None:
        """Object instantiation.  Class requires the existence of a .env file with
        an api key inside.
        
        """

        # TODO: Install some guardrails?  OpenAI will puke if it's not right anyway, so maybe doesn't matter.
        assert load_dotenv('.env') 

        self.book = book
        self.out_path = out_path
        self.model = model
        self.voice = voice
        self.overwrite_protect = overwrite_protect
        # TODO: Should overwrite_protect be an argument to methods or use the class attribute?

    def estimate_cost(self) -> float:        
        """Calculates a cost estimate for using the TTS api to generate an audiobook
        using the provided settings.

        Outputs
        total_cost: The total cost in dollars for a complete audiobook.
        
        """
        total_cost = 0
        for chunk in self.book.chunks:
            num_tokens = math.ceil(len(chunk) / self.token_size)
            chunk_cost = num_tokens * self.cost_per_token[self.model]
            total_cost += chunk_cost
            
        return total_cost
    
    def create_paths_to_mp3s(self, len_of_chunks_list: int, tag: str = '') -> list[Path]:
        """Creates a list of Path objects that store the locations of potential .mp3
        files.  Since OpenAI limits the number of characters in each request, multiple
        .mp3 files will need to be generated for large text files.

        Inputs
        len_of_chunks_list: Integer that tells the method how many paths to generate
        tag: Optional string to append to the file names

        Outputs
        paths: List of Path objects
        
        """
        # Create a list of paths to store .mp3s at.
        # If more than one path is required, order them
        if len_of_chunks_list > 1:
            paths = [self.out_path / 
                    "mp3s" /
                    (self.book.name + f"_{self.voice}_{self.model}_{idx}_of_{len_of_chunks_list}_{tag}.mp3")
                    for idx in range(0, len_of_chunks_list)]
        elif len_of_chunks_list == 1: 
            paths = [self.out_path / 
                    "mp3s" /
                    (self.book.name + f"_{self.voice}_{self.model}_{tag}.mp3")
                    for idx in range(0, len_of_chunks_list)]

        return paths

    def request(self, chunk: str): # TODO:  -> HttpxBinaryResponseContent Does this actually work? Or should I just leave the return type blank?
        """Sends a request to the OpenAI api using settings defined in initialization.

        Inputs
        chunk: A string containing a section of text

        Outputs
        A binary stream containing a .mp3 file

        """

        return client.audio.speech.create(model=self.model,
                                          voice=self.voice,
                                          input=chunk)
    
    def spawn_requests(self, chunks: list[str], paths_to_mp3s: list[Path], overwrite_protect: bool = True) -> list:
        """Manages multiple requests to api such that user time is efficiently used and
        the api usage limits are not exceeded.

        Inputs
        chunks: A list containing each chunk of text to be sent
        paths_to_mp3s: A list specifying where the final mp3s will be stored.  Used
            to make sure already existing files are not overwritten if overwrite_protect
            is True.
        overwrite_protect: Signals whether or not to generate new mp3s even if that content
            may already exist.  Useful for reducing api usage costs when testing.

        Outputs
        responses: A list containing all the binary streams sent by OpenAI to the user.  Contains
            the audio data.
        
        """
        
        # Don't make requests if a expected file already exists and in overwrite_protect mode
        request = [False if overwrite_protect and path.exists() else True
                    for path in paths_to_mp3s]

        # TODO: Integrate joblib here, also find a way to rate limit the requests
        #if len(chunks) < self.max_requests_per_min:
        #    responses = [self.request(chunk) if request[idx] else 0 
        #                 for idx, chunk in enumerate(chunks)]
        
        # Once every 60 seconds, send out a maximum of self.max_requests_per_min requests to OpenAI
        # Can maybe accomplish this using async instead of joblib...
        responses = [0 for chunk in chunks]
        start_time = time.perf_counter()
        num_requests_sent_this_minute = 0
        for idx, chunk in enumerate(chunks):
            current_time = time.perf_counter()
            elapsed_time = current_time - start_time
            # Limit requests per minute
            if elapsed_time < 60.0 and num_requests_sent_this_minute >= self.max_requests_per_min:
                # Hit api per minute usage limits, wait until one minute has passed since start_time
                time.sleep(60.0 - elapsed_time + 5)
                start_time = time.perf_counter()
                num_requests_sent_this_minute = 0 
            elif elapsed_time >= 60.0:
                # If elapsed_time exceeds 60s, reset the time count and request count
                start_time = time.perf_counter()
                num_requests_sent_this_minute = 0

            responses[idx] = self.request(chunk) if request[idx] else 0
            num_requests_sent_this_minute += 1

        return responses
    
    def write_mp3s(self, audio_chunks: list, paths_to_mp3s: list[Path], overwrite_protect: bool = True) -> None:
        # TODO: Should this be merged into spawn_requests? Could simplify code.
        """Writes the binary audio responses to mp3 files while ensuring existing .mp3s are
        protected if desired.

        Inputs
        audio_chunks: A list containing the responses from OpenAI
        paths_to_mp3s: A list containing Path objects that tell the method where to save the .mp3 files to
        overwrite_protect: Signals whether or not to save new mp3s even if that content
            may already exist.

        """

        # Ensure that we don't mismatch audio_chunks to paths_to_mp3s
        assert len(audio_chunks) == len(paths_to_mp3s)

        for idx, chunk in enumerate(audio_chunks):
            if not (overwrite_protect and paths_to_mp3s[idx].exists()):
                # TODO: A chunk might be zero, probably will be filtered out by the if statement
                chunk.stream_to_file(paths_to_mp3s[idx])

    def join_mp3s(self, mp3_path_list: list[Path], overwrite_protect: bool = True) -> None:
        """Uses pydub to join the .mp3 chunks created by write_mp3s into a single mp3 file.

        Inputs
        mp3_path_list: A list containing Path objects that point to the .mp3 files the user wants to join
        overwrite_protect: Signals whether or not to save new mp3s even if that content
            may already exist.

        """

        # Load the mp3 files into AudioSegment objects and then combine them
        mp3_list = [AudioSegment.from_mp3(file) for file in mp3_path_list]
        output_file = mp3_list[0]
        for file in mp3_list[1:]:
            output_file = output_file + file
        
        # Export the full audiobook to a .mp3 file
        out_path = self.create_paths_to_mp3s(1)
        if not (overwrite_protect and out_path.exists()):
            output_file.export(out_path, format="mp3")
    
    def create_audiobook(self) -> None:
        """Takes the book text provided at initialization and the provided settings and 
        converts it into an audiobook.
        
        """

        # TODO: Look into joining the mp3s before they are written to a file, saves on hard drive space
        # Using the AudioSegment __init__ method passing in data=audio_chunk.response.content(), might be able to merge before making files
        # see: httpx/httpx/_models.py::Response
        # openai-python/src/openai/_base_client.py::HttpxBinaryResponseContent

        # Predetermine the paths of output files in case overwrite_protect is True
        paths_to_mp3s = self.create_paths_to_mp3s(len(self.book.chunks))

        # Send the chunks to OpenAI for processing, write responses to mp3s
        audio_chunks = self.spawn_requests(self.book.chunks, paths_to_mp3s, self.overwrite_protect)
        self.write_mp3s(audio_chunks, paths_to_mp3s, self.overwrite_protect)

        # If more than 1 mp3 was created, will need to join the mp3s into a single file
        if len(paths_to_mp3s) > 1:
            self.join_mp3s(paths_to_mp3s, self.overwrite_protect)

    def create_sample(self, chunk_selection: int = 1, sample_size: int = 1000):
        """Creates an audio sample for experimenting with different api options.

        Inputs
        chunk_selection: Integer specifying which chunk out of the list of chunks
            the Book object contains should be used for a sample.
        sample_size: Integer specifying how many characters should be read out of
            the chunk.  Defaults to the api token size.
        
        """

        # Make sure that the chunk_selection is a valid index into self.book.chunks
        chunk_selection = max(min(chunk_selection, len(self.book.chunks)), 0)
        chunk = self.book.chunks[chunk_selection]

        # Make sure that the sample_size is a valid index into the chunk character array
        sample_size = max(min(sample_size, len(chunk)), 5)
        sample = [chunk[0:sample_size]]

        # Create the sample and write it to a .mp3
        path_to_sample = self.create_paths_to_mp3s(1, 'sample')
        audio_chunk = self.spawn_requests(sample, path_to_sample, self.overwrite_protect)
        self.write_mp3s(audio_chunk, path_to_sample, self.overwrite_protect)


if __name__ == "__main__":
    voice = "nova"
    name = "My_Immortal_Ch1-10"
    path_to_book = Path(__file__).parent / "books" / (name+".txt")
    
    book = Book(path_to_book, 4096)
    print(f"Num Chunks: {len(book.chunks)}")
    print(f"Num Chars: {len(book.book_text)}")
    