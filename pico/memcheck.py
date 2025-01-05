import gc
import sys
import os

# Force garbage collection to get accurate memory readings
gc.collect()

# Get memory information
print("\nMemory Information:")
print("-" * 40)
print(f"Free RAM: {gc.mem_free() / 1024:.2f} KB")
print(f"Allocated RAM: {gc.mem_alloc() / 1024:.2f} KB")
print(f"Total RAM: {(gc.mem_alloc() + gc.mem_free()) / 1024:.2f} KB")

# Implementation details
print("\nSystem Information:")
print("-" * 40)
print(f"Implementation: {sys.implementation.name}")
print(f"Version: {'.'.join(str(x) for x in sys.implementation.version)}")
print(f"Platform: {sys.platform}")

# Detailed storage information
print("\nStorage Information:")
print("-" * 40)

try:
    # Get storage stats
    fs_stat = os.statvfs('/')
    
    # Calculate sizes
    block_size = fs_stat[0]  # system block size
    total_blocks = fs_stat[2]  # total blocks
    free_blocks = fs_stat[3]  # free blocks
    
    total_space = block_size * total_blocks
    free_space = block_size * free_blocks
    used_space = total_space - free_space
    
    # Print detailed storage info
    print(f"Total Flash: {total_space / 1024 / 1024:.2f} MB")
    print(f"Used Space: {used_space / 1024 / 1024:.2f} MB")
    print(f"Free Space: {free_space / 1024 / 1024:.2f} MB")
    print(f"Usage: {(used_space / total_space) * 100:.1f}%")
    
    # List files and their sizes
    print("\nFile System Contents:")
    print("-" * 40)
    
    def get_size(path):
        try:
            return os.stat(path)[6]
        except:
            return 0
            
    def print_directory(path, indent=""):
        try:
            for file in os.listdir(path):
                full_path = path + "/" + file if path != "/" else "/" + file
                try:
                    # Try to get file/directory information
                    size = get_size(full_path)
                    is_dir = False
                    try:
                        os.listdir(full_path)
                        is_dir = True
                    except:
                        pass
                        
                    if is_dir:
                        print(f"{indent}📁 {file}/")
                        print_directory(full_path, indent + "  ")
                    else:
                        print(f"{indent}📄 {file}: {size / 1024:.1f} KB")
                except Exception as e:
                    print(f"{indent}❌ Error reading {file}: {str(e)}")
        except Exception as e:
            print(f"Error listing directory {path}: {str(e)}")
    
    print_directory("/")
    
except Exception as e:
    print(f"Error getting storage information: {str(e)}") 