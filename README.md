# 🗳️ Contactless Integrated Voting System (CIVS)

### **A Secure, Inclusive, and Touch-Free Voting System Using Hand Gestures & Speech Recognition**

## 📌 **Overview**
The **Contactless Integrated Voting System (CIVS)** is an innovative, secure, and user-friendly voting platform that enables voters to **cast their votes using speech and hand gestures**. This project is designed to ensure **safe and accessible voting**, eliminating the need for physical contact while also providing support for physically challenged individuals.

CIVS offers two distinct voting modes:
- 🎙️ **AGVS (Audio-Based Voting System)** – Voters cast their vote using speech recognition.
- ✋ **HGVS (Hand Gesture-Based Voting System)** – Voters cast their vote using predefined hand gestures.

This project has been **patented** and is currently in the **published stage**, awaiting grant approval.  
**Patent Number**: *[To be added]*  
**Patent Status**: *Published, yet to be granted*  

For any inquiries, please contact **anirudhvasudevan11@gmail.com**.

---

## 📂 **Project Structure**
📁 Contactless-Integrated-Voting-System
│── 📁 abc/                     # Hand gesture images (A-Z)
│── 📁 model/                   # ML model for gesture recognition
│── 📄 main.py                  # Main script for running the system
│── 📄 signdetect.py            # Hand gesture detection module
│── 📄 model.h5                 # Pre-trained deep learning model for gesture recognition
│── 📄 requirements.txt         # Python dependencies
│── 📄 README.md                # Documentation

---

## 🔧 **Installation & Setup**
### **1️⃣ Install Python (Recommended: Python 3.10)**
Ensure **Python 3.10** is installed on your system:
```
python3 --version

```
### **2️⃣ Clone the Repository
```
git clone https://github.com/YOUR_USERNAME/Contactless-Integrated-Voting-System.git
cd Contactless-Integrated-Voting-System
```

### **2️⃣ Create a Virtual Environment
```
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate  # Windows
```
### **4️⃣ Install Dependencies
```
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

```
### **5️⃣ Run the Program
```
python main.py
```



📂 Training Data & Model Details

All the data used for training the model, including training accuracy, validation accuracy, and loss metrics, is available in this GitHub repository. Additionally, a Google Drive link will be provided where you can access all necessary training datasets, model files, and experimental results.

🔗 Google Drive Link: [To be added]



🏗️ How It Works

1️⃣ The voter selects Audio (AGVS) or Gesture (HGVS) voting.
2️⃣ If AGVS is chosen, the voter speaks the number assigned to a party.
3️⃣ If HGVS is chosen, the voter performs a hand gesture representing a party.
4️⃣ The system reconfirms the vote before finalizing.
5️⃣ The vote is securely cast and recorded.


📄 License & Patent

This project is patented and is currently in the published stage, awaiting grant approval.
Patent Number: [To be added]
Patent Status: Published, yet to be granted

For any questions or support, feel free to reach out to anirudhvasudevan11@gmail.com.
