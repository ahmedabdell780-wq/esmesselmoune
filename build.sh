#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

if [ -f apps.zip ]; then
    echo "Extracting apps.zip..."
    unzip -o apps.zip -d apps/
    echo "Files in apps:"
    ls -la apps/
else
    echo "ERROR: apps.zip NOT FOUND!"
    exit 1
fi

if [ -f media.zip ]; then
    echo "Extracting media.zip..."
    unzip -o media.zip -d media/
fi

python manage.py collectstatic --no-input
python manage.py migrate

# إنشاء حساب المدير تلقائياً
if [ -f create_admin.py ]; then
    python create_admin.py
fi

if [ -f fix_admin.py ]; then
    python fix_admin.py
fi
