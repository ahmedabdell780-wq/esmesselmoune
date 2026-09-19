import re

# Read current book.html
with open('templates/tournaments/book.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace footers to add page-num span
target = "<span>{{ site_settings.app_name|upper }} \u00b7 {{ tournament.year }}</span>"
replacement = "<span>{{ site_settings.app_name|upper }} \u00b7 {{ tournament.year }}</span><span class=\"page-num\"></span>"
content = content.replace(target, replacement)

# 2. Define the new photo gallery page html
photo_gallery_html = """
    <!-- PAGE 13: PHOTO GALLERY (معرض صور البطولة) -->
    {% if other_awards_media %}
    <div class="page-container page-break flex flex-col justify-between">
        <div>
            <div class="border-b-4 border-[#C5A028] pb-4 mb-8">
                <h2 class="text-3xl font-black text-slate-900">معرض صور البطولة</h2>
                <p class="text-slate-500 font-bold tracking-widest uppercase">Galerie Photos de la Compétition / Tournament Gallery</p>
            </div>

            <div class="grid grid-cols-3 gap-6">
                {% for mm in other_awards_media|slice:":9" %}
                <div class="avoid-break bg-slate-50 rounded-2xl border border-slate-200 p-3 shadow-sm flex flex-col justify-between" style="aspect-ratio: 0.95;">
                    <div class="w-full aspect-[4/3] rounded-xl overflow-hidden border border-slate-200/60 bg-slate-100 flex items-center justify-center relative">
                        <img src="{{ mm.file.url }}" class="w-full h-full object-cover">
                    </div>
                    {% if mm.cleaned_title %}
                    <p class="text-[10px] text-slate-600 font-black text-center mt-2 px-1 line-clamp-2" dir="rtl">{{ mm.cleaned_title }}</p>
                    {% else %}
                    <p class="text-[9px] text-slate-400 text-center mt-2 italic">لقطة من البطولة / Match Moment</p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="mt-8 pt-4 border-t border-slate-200 flex justify-between items-center text-xs text-slate-400 font-bold">
            <span>{{ site_settings.app_name|upper }} \u00b7 {{ tournament.year }}</span><span class="page-num"></span>
            <span>معرض الصور / Galerie Photos</span>
        </div>
    </div>
    {% endif %}
"""

# Insert right before PAGE 13: SIGNATURES
target_signatures = "<!-- PAGE 13: SIGNATURES"
content = content.replace(target_signatures, photo_gallery_html + "\n    " + target_signatures)

# Write updated book.html
with open('templates/tournaments/book.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done updating templates/tournaments/book.html!")
