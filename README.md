# ⚡️ ComboSorter

A high-performance Python toolkit for processing and sorting large structured text datasets. Optimised for speed and memory efficiency on high-volume files.

---

## 🚀 Highlights

- **Streaming Architecture**: Processes files line-by-line. Handle multi-gigabyte files without crashing your RAM.
- **Module Chaining**: Apply multiple transformations in a single pass (e.g., Sanitize → Filter → Dedupe).
- **GNU Sort Integration**: Uses external `gsort` for near-instant deduplication and alphabetization on high-end hardware.
- **Case Preservation**: Intelligently handles email normalization while preserving password case sensitivity.
- **Safe Sanitization**: Conservative regex scripts to clean malformed emails without losing valid data.

---

## 🛠 Installation & Setup

No complex installation is required. This is a standalone Python utility.

### Requirements:
- Python 3.8+
- (Optional) **GNU Coreutils**: Recommended for the fastest deduplication on macOS/Linux.
  ```bash
  # macOS
  brew install coreutils
  ```

### Running the Tool:

**Interactive Mode:**
```bash
python3 main.py
```

**Batch / CLI Mode:**
```bash
# Process a file with Extract E:P (H) and Remove Duplicates (G) without interactive prompts
python3 main.py --input messy_logs.txt --modules H,G --out-dir ./output
```

---

## 🧩 Available Modules

| Key | Module | Description |
| :--- | :--- | :--- |
| **0** | **Normal Edit** | Trims whitespace and removes empty lines. |
| **1** | **Strong Edit** | Basic email validation + conservative sanitization. |
| **2** | **Extreme Edit** | Strict validation + Sanitization + Lowercase Email + Email/Pass Dedupe. |
| **3** | **Capitalize** | Converts the email/username part to UPPERCASE. |
| **4** | **Decapitalize** | Converts the email/username part to lowercase. |
| **5** | **Randomize** | Shuffles the list (⚠️ requires RAM for the shuffle). |
| **6** | **Alphabetize** | Sorts the list (uses `gsort` if available). |
| **7** | **Domain Filter** | Keep only lines matching a specific domain (e.g., `gmail.com`). |
| **8** | **Country Filter** | Keep only lines matching a TLD/Country code (e.g., `.fr`). |
| **9** | **U/P to E/P** | Converts `user:pass` to `user@domain:pass`. |
| **A** | **E/P to U/P** | Drops the domain, converting `user@domain:pass` to `user:pass`. |
| **B** | **Custom Append** | Appends a custom string to either the Left or Right part. |
| **C** | **Password Length** | Filters combos based on a Min/Max password length range. |
| **D** | **Email Length** | Filters combos based on a Min/Max email/username length. |
| **E** | **Remove Custom** | Removes specific characters or Regex patterns from either part. |
| **F** | **Split Domain** | Breaks a single large list into individual `{domain}.txt` files. |
| **G** | **Remove Duplicate** | High-speed deduplication (supports `gsort` parallel processing). |
| **H** | **Extract E:P** | Extracts valid `email:password` pairs from messy/unstructured logs. |
| **I** | **Domain Stats** | Analyzes and displays statistics for the top 20 domains in the list. |

---

## 💡 Advanced Usage: Chaining

ComboSorter supports **sequential chaining**. Instead of running one operation at a time, you can input a comma-separated list of modules.

**Example: `2,G,6`**
1. **Extreme Edit**: Clean and normalize the list.
2. **Remove Duplicate**: Ensure every line is unique.
3. **Alphabetize**: Produce a perfectly ordered final result.

---

## ⚙️ Configuration (Environment Variables)

You can customize the engine behavior by setting environment variables before running the script:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `COMBOSORTER_SANITIZE` | `1` | Set to `0` to disable auto-cleaning of emails. |
| `COMBOSORTER_STRICT` | `0` | Set to `1` to enable very strict RFC-style email validation. |
| `COMBOSORTER_LOG_LEVEL` | `INFO` | Set to `DEBUG` for detailed processing logs. |

---

## 🛡 License & Safety
- **Keep Backups**: Always keep a copy of your source `.txt` files. 
- **Encoding**: The tool defaults to UTF-8 with `ignore` for invalid characters to ensure non-stop processing of messy lists.

---
*Developed with focus on performance and reliability.*
