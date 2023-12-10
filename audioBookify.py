# -*- coding: utf-8 -*-
"""
Created on Thu Nov  9 16:19:04 2023

@author: Daniel

"""
import math
import time
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
    
    max_requests_per_min = 50
    
    def __init__(self, book, out_path, model = "tts-1", voice = "onyx", overwrite_protect = True):
        
        self.book = book
        self.out_path = out_path
        self.model = model
        self.voice = voice
        self.overwrite_protect = overwrite_protect
    
    def estimate_cost(self):
        token_size = 1000 # characters
        cost_per_token = {"tts-1": 0.015, "tts-1-hd": 0.03}
        
        total_cost = 0
        for chunk in self.book.chunks:
            num_tokens = math.ceil(len(chunk) / token_size)
            chunk_cost = num_tokens * cost_per_token[self.model]
            total_cost += chunk_cost
            
        return total_cost
    
    def request(self, chunk):
        
        return client.audio.speech.create(model=self.model,
                                          voice=self.voice,
                                          input=chunk)
    
    def spawn_requests(self):
        
        # Integrate joblib here, also find a way to rate limit the requests
        if len(self.book.chunks) < 50:
            responses = [self.request(chunk) for chunk in self.book.chunks]
        
        return responses
    
    def write_mp3s(self, audiobook_chunks):
        
        pass
    
    def join_mp3s(self, mp3_path_list):
        
        if len(book.chunks) > 1:
            mp3_list = [AudioSegment.from_mp3(file) for file in mp3_path_list]
            output_file = mp3_list[0]
            for file in mp3_list[1:]:
                output_file = output_file + file
        
        # This needs to be rewritten
        output_file.export(Path(__file__).parent / "mp3s" / (name + f"_{self.voice}.mp3"), format="mp3")
    
    def create_audiobook(self):
        
        audiobook_chunks = self.spawn_requests()
        mp3_path_list = self.write_mp3s(audiobook_chunks)
        self.join_mp3s(mp3_path_list)

    def create_sample(self):

        pass
        


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