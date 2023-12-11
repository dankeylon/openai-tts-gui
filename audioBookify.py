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
    
    disclaimer = "Note: This audio recording was generated using an AI voice provided by Open-AI. \n"
    
    def __init__(self, path_to_book, chunk_size = 4096):
        
        # Read Book
        self.path_to_book = path_to_book
        self.name = path_to_book.stem
        
        with open(self.path_to_book, 'r', errors="ignore") as f:
            
            book_text = f.readlines()
            
        book_text = [self.disclaimer] + book_text
        self.book_text = ' '.join(book_text)
        self.chunks = self.chunk_book(self.book_text, chunk_size)
        
    def chunk_book(self, book_text, chunk_size):
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
    
    # Usage details from 
    max_requests_per_min = 50
    token_size = 1000
    cost_per_token = {"tts-1": 0.015, "tts-1-hd": 0.03}
    
    def __init__(self, book, out_path, model = "tts-1", voice = "onyx", overwrite_protect = True):
        
        assert load_dotenv('.env')

        self.book = book
        self.out_path = out_path
        self.model = model
        self.voice = voice
        self.overwrite_protect = overwrite_protect

    def estimate_cost(self):        
        
        total_cost = 0
        for chunk in self.book.chunks:
            num_tokens = math.ceil(len(chunk) / self.token_size)
            chunk_cost = num_tokens * self.cost_per_token[self.model]
            total_cost += chunk_cost
            
        return total_cost
    
    def create_paths_to_mp3s(self, len_of_chunks_list, sample = False):
        # TODO: Make paths relative to self.out_path
        if sample == True:
            sample_text = 'sample'
        else:
            sample_text = ''

        if len_chunks_list > 1:
            paths = [Path(__file__).parent / 
                    "mp3s" /
                    (self.book.name + f"_{self.voice}_{self.model}_{idx}_of_{len_of_chunks_list}_{sample_text}.mp3")
                    for idx in range(0, len_of_chunks_list)]
        elif len_chunks_list == 1: 
            paths = [Path(__file__).parent / 
                    "mp3s" /
                    (self.book.name + f"_{self.voice}_{self.model}_{sample_text}.mp3")
                    for idx in range(0, len_of_chunks_list)]

        return paths

    def request(self, chunk):
        
        return client.audio.speech.create(model=self.model,
                                          voice=self.voice,
                                          input=chunk)
    
    def spawn_requests(self, chunks, paths_to_mp3s):
        
        # Don't make requests if a expected file already exists and in overwrite_protect mode
        request = [False if self.overwrite_protect and path.exists() else True
                    for path in paths_to_mp3s]

        # Integrate joblib here, also find a way to rate limit the requests
        if len(chunks) < self.max_requests_per_min:
            responses = [self.request(chunk) if request[idx] else 0 
                         for idx, chunk in enumerate(chunks)]
        
        return responses
    
    def write_mp3s(self, audiobook_chunks, paths_to_mp3s, overwrite_protect = True):
        
        assert len(audiobook_chunks) == len(paths_to_mp3s)

        for idx, chunk in enumerate(audiobook_chunks):
            if not (overwrite_protect and paths_to_mp3s[idx].exists()):
                chunk.stream_to_file(paths_to_mp3s[idx])

    def join_mp3s(self, mp3_path_list, overwrite_protect = True):
        # Use pydub to join the .mp3 chunks created by write_mp3s
        mp3_list = [AudioSegment.from_mp3(file) for file in mp3_path_list]
        output_file = mp3_list[0]
        for file in mp3_list[1:]:
            output_file = output_file + file
        
        # Export the full audiobook to a .mp3 file
        out_path = self.create_paths_to_mp3s(1)
        if not (overwrite_protect and out_path.exists()):
            output_file.export(out_path, format="mp3")
    
    def create_audiobook(self):
        # TODO: Look into joining the mp3s before they are written to a file, saves on hard drive space

        # Predetermine the paths of output files in case overwrite_protect is True
        paths_to_mp3s = self.create_paths_to_mp3s(len(self.book.chunks))

        # Send the chunks to OpenAI for processing, write responses to mp3s
        audio_chunks = self.spawn_requests(self.book.chunks, paths_to_mp3s)
        self.write_mp3s(audio_chunks, paths_to_mp3s, self.overwrite_protect)

        # If more than 1 mp3 was created, will need to join the mp3s into a single file
        if len(paths_to_mp3s) > 1:
            self.join_mp3s(paths_to_mp3s, self.overwrite_protect)

    def create_sample(self, chunk_selection = 1, sample_size = 1000):

        chunk = [self.book.chunks[chunk_selection][0:sample_size]]
        path_to_sample = self.create_paths_to_mp3s(len(chunk), sample = True)
        audio_chunk = self.spawn_requests(chunk, path_to_sample)
        self.write_mp3s(audio_chunk, path_to_sample, self.overwrite_protect)

        


if __name__ == "__main__":
    voice = "nova"
    name = "My_Immortal_Ch1-10"
    path_to_book = Path(__file__).parent / "books" / (name+".txt")
    
    book = Book(path_to_book, 4096)
    print(f"Num Chunks: {len(book.chunks)}")
    print(f"Num Chars: {len(book.book_text)}")
    
    
    idx = 0
    speech_files = []
    for chunk in book.chunks:
        
        print(chunk)

        if len(book.chunks) == 1:
            speech_file_path = Path(__file__).parent / "mp3s" / (name + f"_{voice}.mp3")
        else: 
            speech_file_path = Path(__file__).parent / "mp3s" / (name + f"_{voice}_{idx}.mp3")
        
        if not speech_file_path.exists(): # Try not to bleed me dry on api charges
            response = client.audio.speech.create(
              model="tts-1",
              voice=voice,
              input=chunk
            )
            
            response.stream_to_file(speech_file_path)
        
        idx = idx + 1
        speech_files.append(speech_file_path)
    
    if len(book.chunks) > 1:
        mp3_list = [AudioSegment.from_mp3(file) for file in speech_files]
        output_file = mp3_list[0]
        for file in mp3_list[1:]:
            output_file = output_file + file
            
        output_file.export(Path(__file__).parent / "mp3s" / (name + f"_{voice}.mp3"), format="mp3")