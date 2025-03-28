import os
import sys
import time
import random
import string

def random_string(length=8):
    """Generate a random string of given length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def create_nested_structure(base_dir, depth=3, width=3):
    """
    Recursively creates nested directories with random files.

    :param base_dir: Root directory
    :param depth: Maximum depth of nesting
    :param width: Maximum number of subdirectories per level
    """
    if depth <= 0:
        return

    for _ in range(random.randint(1, width)):  # Randomize number of subdirectories
        sub_dir = os.path.join(base_dir, random_string())
        os.makedirs(sub_dir, exist_ok=True)
        print(f"[Created Folder] {sub_dir}")

        # Randomly create some files in the directory
        for _ in range(random.randint(1, width)):  
            file_path = os.path.join(sub_dir, random_string() + ".txt")
            with open(file_path, "w") as f:
                f.write(random_string(random.randint(10, 1000)))  # Random content size
            print(f"[Created File] {file_path}")

        # Recurse deeper
        create_nested_structure(sub_dir, depth-1, width)

def nested_file_creator(directory, rate=1, depth=3, width=3):
    """
    Creates a deeply nested file structure with random files.

    :param directory: Path where files should be created
    :param rate: Number of nested structures to create per second
    :param depth: Depth of nested directories
    :param width: Number of files and directories at each level
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    print(f"Creating {rate} nested structures per second in: {directory}")

    while True:
        for _ in range(rate):
            create_nested_structure(directory, depth, width)
        time.sleep(1)  # Control rate

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python nested_file_creator.py <directory> [rate] [depth] [width]")
        sys.exit(1)

    directory_to_watch = sys.argv[1]
    rate = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # Default: 1 structure per second
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 3  # Default: 3 levels deep
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 3  # Default: 3 files/folders per level

    nested_file_creator(directory_to_watch, rate, depth, width)
