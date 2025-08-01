import pandas as pd
import os

# Define the file path (use raw string to avoid Unicode escape issues)
file_path = r"C:\Users\Priya Duraivel\OneDrive\Desktop\messages.csv"
output_path = r"C:\Users\Priya Duraivel\OneDrive\Desktop\processed_messages.csv"

# Check if the file exists before trying to read
if not os.path.exists(file_path):
    print(f"❌ Error: File '{file_path}' not found.")
else:
    try:
        # Read the CSV file
        df = pd.read_csv(file_path, encoding="utf-8")  
        
        # Display first few rows
        print("📄 First few rows of the file:")
        print(df.head())  

        # Save the processed file
        df.to_csv(output_path, index=False)
        print(f"✅ Processed file saved at: {output_path}")

    except Exception as e:
        print(f"❌ Error reading or processing the CSV file: {e}")
