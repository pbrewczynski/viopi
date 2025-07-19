import argparse                                                                                                         
import json                                                                                                             
import os                                                                                                               
import sys                                                                                                              
from datetime import datetime                                                                                           
                                                                                                                        
# Assuming these modules exist based on SOURCES.txt                                                                     
from . import viopi_utils                                                                                               
from .viopi_help import print_help_and_exit                                                                                    
from .viopi_version import get_project_version, print_version_and_exit                                                                              
                                                                                                                        
def main():                                                                                                             
    """Main function to run the viopi tool."""                                                                          
    parser = argparse.ArgumentParser(                                                                                   
        description="Viopi: View I/O and Project Info.",                                                                
        add_help=False # Custom help message                                                                            
    )                                                                                                                   
    parser.add_argument(                                                                                                
        "path",                                                                                                         
        nargs="?",                                                                                                      
        default=".",                                                                                                    
        help="Directory path to process. Defaults to the current directory."                                            
    )                                                                                                                   
    parser.add_argument(                                                                                                
        "-h", "--help",                                                                                                 
        action="store_true",                                                                                            
        help="Show this help message and exit."                                                                         
    )                                                                                                                   
    parser.add_argument(                                                                                                
        "--stdout",                                                                                                     
        action="store_true",                                                                                            
        help="Print the output to stdout instead of copying to clipboard."                                              
    )                                                                                                                   
    parser.add_argument(                                                                                                
        "--json",                                                                                                       
        action="store_true",                                                                                            
        help="Output the data in JSON format."                                                                          
    )                                                                                                                   
    parser.add_argument(                                                                                                
        "-v", "--version",                                                                                              
        action="store_true",                                                                                            
        help="Show program's version number and exit."                                                                  
    )                                                                                                                   
                                                                                                                        
    args = parser.parse_args()                                                                                          
                                                                                                                        
    if args.help:                                                                                                       
        print_help_and_exit()
        sys.exit(0)                                                                                                     
                                                                                                                        
    if args.version:                                                                                                    
        print_version_and_exit()
        # print(f"viopi version {VIOPION_VERSION}")                                                                       
        sys.exit(0)                                                                                                     
                                                                                                                        
    target_dir = os.path.abspath(args.path)                                                                             
                                                                                                                        
    if not os.path.isdir(target_dir):                                                                                   
        print(f"Error: Directory not found at '{target_dir}'")                                                          
        sys.exit(1)                                                                                                     
                                                                                                                        
    # --- Data Collection ---                                                                                           
    files_to_process = viopi_utils.get_file_list(target_dir)                                                            
                                                                                                                        
    file_data_list = []                                                                                                 
    stats = {                                                                                                           
        "total_files": 0,                                                                                               
        "total_lines": 0,                                                                                               
        "total_characters": 0                                                                                           
    }                                                                                                                   
                                                                                                                        
    for file_path in files_to_process:                                                                                  
        try:                                                                                                            
            with open(file_path, 'r', encoding='utf-8') as f:                                                           
                content = f.read()                                                                                      
                                                                                                                        
            relative_path = os.path.relpath(file_path, target_dir)                                                      
                                                                                                                        
            # Update stats                                                                                              
            stats["total_files"] += 1                                                                                   
            stats["total_lines"] += len(content.splitlines())                                                           
            stats["total_characters"] += len(content)                                                                   
                                                                                                                        
            # Add to file data list                                                                                     
            file_data_list.append({                                                                                     
                "path": relative_path,                                                                                  
                "content": content                                                                                      
            })                                                                                                          
                                                                                                                        
        except (IOError, UnicodeDecodeError) as e:                                                                      
            print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)                                    
            continue                                                                                                    
                                                                                                                        
    # --- Output Generation ---                                                                                         
    if args.json:                                                                                                       
        # JSON Output Mode                                                                                              
        output_data = {                                                                                                 
            "stats": stats,                                                                                             
            "files": file_data_list                                                                                     
        }                                                                                                               
        # Use indent for pretty-printing the JSON                                                                       
        output_string = json.dumps(output_data, indent=2)                                                               
    else:                                                                                                               
        # Original Text Output Mode                                                                                     
        header = f"Directory Processed: {target_dir}\n"                                                                 
        tree_output = viopi_utils.generate_tree_output(target_dir, files_to_process)                                    
                                                                                                                        
        file_contents_str = "\n\n---\nCombined file contents:\n"                                                        
        for file_data in file_data_list:                                                                                
            file_contents_str += f"\n--- FILE: {file_data['path']} ---\n{file_data['content']}"                         
                                                                                                                        
        output_string = header + tree_output + file_contents_str + "\n\n--- End of context ---"                         
                                                                                                                        
    # --- Final Output Handling ---                                                                                     
    if args.stdout or args.json:                                                                                        
        print(output_string)                                                                                            
    else:                                                                                                               
        try:                                                                                                            
            import pyperclip                                                                                            
            pyperclip.copy(output_string)                                                                               
            print("Viopi output copied to clipboard.")                                                                  
            print(f"Stats: {stats['total_files']} files, {stats['total_lines']} lines, {stats['total_characters']} characters.")                                                                                                           
        except pyperclip.PyperclipException as e:                                                                       
            print(f"Error: Could not copy to clipboard. Please install xclip or xsel on Linux, or use the --stdout flag.")                                                                                                                      
            print(f"Pyperclip error: {e}")                                                                              
            sys.exit(1)                                                                                                 
                                                                                                                        
if __name__ == "__main__":                                                                                              
    main()                              