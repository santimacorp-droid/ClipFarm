#!/usr/bin/env python3
"""
Script for installing multi-model provider dependencies
"""
import subprocess
import sys
import os

def install_package(package):
    """InstallPythonPackage"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Install {package} Failed: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Starting to install multi-model provider dependencies...")
    
    # Packages to install
    packages = [
        "openai>=1.0.0",           # OpenAI
        "google-genai>=1.0.0",     # Google Gemini (Unified version GenAI SDK)
        "requests>=2.25.0",        # SiliconFlow (HTTPRequest)
        "dashscope>=1.10.0",       # Ali Cloud Tianyi Qianwen (if not already installed))
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print(f"\n📊 Installation result: {success_count}/{total_count} package(s) successfully installed")
    
    if success_count == total_count:
        print("🎉 All dependencies installed! You can now use multi-model provider features. ")
        print("\n📝 Getting started:")
        print("1. Boot system: python backend/main.py")
        print("2. Configure via the settings pageAPIKey")
        print("3. Choose your preferredAIModel provider")
        print("4. Start usingAIAutomatic slicing feature")
    else:
        print("⚠️  Some dependencies failed to install. Please check the network connection or manually install the failed packages. ")
        print("Manual installation command:")
        for package in packages:
            print(f"  pip install {package}")

if __name__ == "__main__":
    main()
