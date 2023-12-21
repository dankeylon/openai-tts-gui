# -*- coding: utf-8 -*-
"""
Created on Thu Nov  9 16:19:04 2023

@author: Daniel

"""
# TODO: What happens if you give the api a chunk that is larger than 4096 characters?
# TODO: What happens if you exceed the per-minute api request limits?
import math
import time
import asyncio
import aiohttp
import pickle

from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI

def subslices(lst: list, n: int) -> list:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

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

        assert load_dotenv('.env')
        self.client = OpenAI() 

        self.book = book
        self.out_path = out_path
        self.model = model
        self.voice = voice
        self.overwrite_protect = overwrite_protect

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
    
    def create_path_to_mp3(self, tag: str = '') -> Path:
        """Creates a Path object that stores the location of a potential .mp3
        file.

        Inputs
        tag: Optional string to append to the file name

        Outputs
        path: Path object
        
        """
        # Create a path to store .mp3s at. 
        return self.out_path / "mp3s" / (self.book.name + f"_{self.voice}_{self.model}_{tag}.mp3")

    async def request(self, chunk: str):
        """Sends a request to the OpenAI api using settings defined in initialization.

        Inputs
        chunk: A string containing a section of text

        Outputs
        A binary stream containing a .mp3 file

        """

        return self.client.audio.speech.create(model=self.model, voice=self.voice, input=chunk)
    
    async def spawn_requests(self, chunks: list[str]) -> list:
        """Manages multiple requests to api such that user time is efficiently used and
        the api usage limits are not exceeded.

        Inputs
        chunks: A list containing each chunk of text to be sent

        Outputs
        responses: A list containing all the binary streams sent by OpenAI to the user.  Contains
            the audio data.
        
        """
        
        async with aiohttp.ClientSession() as session:
            requests = [self.request(chunk) for chunk in chunks]
            responses = []

            # Once every 60 seconds, send out a maximum of self.max_requests_per_min requests to OpenAI
            for request_batch in subslices(requests, self.max_requests_per_min):
                start_time = time.perf_counter()

                responses += await asyncio.gather(*request_batch)

                current_time = time.perf_counter()
                elapsed_time = current_time - start_time

                if elapsed_time <= 60.0:
                    time.sleep(60.0 - elapsed_time + 5)

        return responses
    
    def write_mp3(self, responses: list, out_path: Path) -> None:
        """Writes the binary audio responses to an mp3 file

        Inputs
        audio_chunks: A list containing the responses from OpenAI
        out_path: Path object for file output destination
        """

        # Combine the responses into a single byte array.
        audio_chunks = []
        for response in responses:
            mp3 = b''
            for data in response.iter_bytes(None):
                mp3 += data
            audio_chunks += [mp3]

        mp3_out = b''.join(audio_chunks)

        # Write byte array to an mp3 file
        with open(out_path, 'wb') as f:
            f.write(mp3_out)
    
    def create_audiobook(self, cache_responses: bool=False) -> None:
        """Takes the book text provided at initialization and the provided settings and 
        converts it into an audiobook.

        Inputs
        cache_responses: Flag to control caching responses in pickle file for debugging
        
        """

        assert not (self.create_path_to_mp3().exists() and self.overwrite_protect)

        # Send the chunks to OpenAI for processing, write responses to an mp3
        pickle_path = self.out_path / "responses.pickle"
        if pickle_path.exists() and cache_responses:
            with open(pickle_path, 'rb') as f:
                responses = pickle.load(f)
        elif not pickle_path.exists() and cache_responses:
            responses = asyncio.run(self.spawn_requests(self.book.chunks))
            with open(pickle_path, 'wb') as f:
                pickle.dump(responses, f)
        else:
            responses = asyncio.run(self.spawn_requests(self.book.chunks))

        self.write_mp3(responses, self.create_path_to_mp3())

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
        audio_chunk = asyncio.run(self.spawn_requests(sample))
        self.write_mp3(audio_chunk, self.create_path_to_mp3('sample'))


if __name__ == "__main__":
    # Early testing code
    voice = "nova"
    name = "My_Immortal_Ch1-10"
    path_to_book = Path(__file__).parent / "books" / (name+".txt")
    
    book = Book(path_to_book, 4096)
    print(f"Num Chunks: {len(book.chunks)}")
    print(f"Num Chars: {len(book.book_text)}")
    print(f"Num Tokens: {int(len(book.book_text)/1000) + 1}")

    out_path = Path(__file__).parent 
    api = TTS_API_Wrapper(book, out_path, model = "tts-1", voice = voice, overwrite_protect = True)
    print(f"Estimated Cost: {api.estimate_cost()}$")

    go = input("Make Sample? [y/n]")
    if go == 'y':
        api.create_sample()

    go = input("Make audiobook? [y/n]")
    if go == 'y':
        api.create_audiobook(cache_responses=True)



    