# Công thức kể theo chủ đề (R9) — sẵn để làm prompt

Nguồn số liệu: 83 video @mcgi.o (matrix.json + transcript Whisper). Cảnh báo chung:
- Transcript gồm cả lời clip tin tức của người khác (48/83 video có hook `news_clip_other_audio`), nên "độ dài câu/câu mở/câu kết" là của lời nói nghe được, không hoàn toàn là giọng kể của kênh.
- 53/83 video kết "abrupt" (cắt giữa chừng ở ~66 s, 16 video câu cuối không có dấu chấm): đây là hạn chế cắt clip, KHÔNG nên bắt chước.
- Nhóm chồng lấn nhau và nhỏ; lượt xem lệch rất mạnh (trung vị toàn kênh 6.143, trung bình 113.269, một video 3,8 triệu). Chỉ dùng trung vị, không dùng trung bình. n < 10 coi là giai thoại, không phải quy luật.
- Phân nhóm: "tội phạm" = murder, child_victim, missing, court, accident (n=59); "scandal người nổi tiếng" = influencer_drama + celebrity_gossip (n=22); "trend/viral" (n=3), "hồ sơ cũ" (n=4), "chết/sức khoẻ người nổi tiếng" (n=14, lọc từ khoá died/passed away/hospital) là nhóm lọc từ khoá, n rất nhỏ.

## Số đo chung (toàn kênh, n=83)
- ~199 từ/video, ~201 wpm, ~11 câu, câu trung bình 23,7 từ (viral: 17,0 từ; normal: 25,7 từ).
- Video viral (n=14, ≥10x trung vị): câu NGẮN hơn, wpm thấp hơn (191 vs 203), 50% kết bằng câu tóm tắt/đạo đức (`summary_or_moral`) so với 16% ở nhóm normal. Kết bằng tóm tắt: trung vị 12.700 lượt xem (n=19) so với abrupt 5.446 (n=53); cliffhanger 23.900 (n=6); CTA 23.600 (n=2).
- Câu kết là câu hỏi: 2/83 (2,4%), trung vị 3.414 lượt (n=2, vô nghĩa thống kê). Có câu hỏi ở đâu đó trong lời: 17/83. Kênh gần như KHÔNG kết bằng câu hỏi: đây là yêu cầu mới của user, không phải bắt chước.
- Nêu nguồn: chỉ 18/83 video có cụm nguồn tường minh ("according to reports/investigators/TMZ", "police say", "prosecutors say", "authorities say"). Nguồn ngắn, nhét giữa câu, không dẫn dài.
- Cảm xúc (trung vị lượt xem; n): sympathy 22.900 (9), suspense 21.300 (7), curiosity 10.814 (14), grief 9.365 (16), outrage 5.724 (14), shock 4.579 (22), humor 1.855 (1). Viral theo cảm xúc: sympathy 4/9, grief 3/16, curiosity 3/14, shock 2/22, suspense 2/7, outrage 0/14. Hài hước chỉ n=1 (từ khoá lol/funny: 1/83): kênh gần như không dùng hài; dùng thì coi là thử nghiệm.
- Ý nghĩa: thương tâm/đồng cảm và hồi hộp/tò mò cho trung vị cao nhất; phẫn nộ và sốc nhiều bài nhưng ít viral. Nghĩa là "sốc" nên là chất liệu mở bài, "thương tâm" nên là âm cuối.

## 1. Tội phạm (n=59; trung vị 5.398; viral 12%)
Đo: ~198 từ, câu 26,5 từ (dài, kiểu bản tin), 10,3 câu; tone: shock 21, grief 12, outrage 9, suspense 7; phong cách: third_person_news 29, mixed 17, first_person 9.
- Câu 1: dài ~29 từ, nêu ngay ai, làm gì, ở đâu, tình trạng pháp lý. Mẫu thật: "A 36 year old transgender man has been arrested and charged with murder after his mother was found dead inside a Laguna Beach, California home." / "A former PhD student was facing the DP for taking the life of a newborn and injuring the twin, but she's now accepted a plea deal." / "Hey guys, so we have a developing story coming out of Massachusetts, a 17 year old teenager is accused of killing his mom and younger brother..." / "Man, so Lil Durk's murder for hire trial is set to begin..." (573K) / "This precious little boy was headbutted by his own father and the video is going viral." (3,8M, trường hợp cực trị về nạn nhân trẻ em).
- Thân: dòng thời gian theo thứ tự (phát hiện, bắt giữ, cáo buộc), nguồn "police say / according to investigators" chèn giữa câu.
- Câu kết thật: "Just absolutely devastating to watch." (3,8M) / "With that, she pleads guilty and was sentenced to six years in prison." / "Obviously, I'll keep you guys posted." / "Facts." / "I don't see either one of them getting out any time soon." Kết bằng câu hỏi: 1/59.
- Prompt (EN):
```
Write a 62-68 second (about 195-205 words) American-English narration in the voice of a fast, serious news explainer. Sentence 1 (<=28 words): who, what, where, legal status, with the single most shocking fact first. Sentences 2-4: strict chronology (discovery, arrest, charge), one attribution phrase per 3-4 sentences, short and inline ("police say", "according to investigators", "prosecutors allege"); never present an allegation as proven. Body: short sentences (avg 15-20 words), at most one sentence over 30 words. Climax (sentence ~8-9): the most disturbing or outrageous detail, delivered flat and factual. Close with TWO sentences: (a) a one-line human-cost beat (sympathy or grief for the victim); (b) a final doubtful question that does not assert guilt, e.g. "But if that is true, why did no one stop it?" End ON the question. Never finish mid-sentence. No jokes.
```
- Giải thích: bản tin tội phạm của kênh dài câu, nghiêm; để "viral" hơn nên rút câu (viral có câu ngắn hơn ~9 từ so với normal), và đặt nhịp thương tâm trước câu hỏi cuối để không tụt cảm xúc.

## 2. Scandal người nổi tiếng/influencer (n=22; trung vị 11.214; viral 32%)
Đo: ~204 từ, câu 17,1 từ (ngắn, đối thoại), 12,9 câu; tone: curiosity 8, sympathy 5, outrage 5, grief 4; style: first_person_commentary 9. Tỉ lệ kết tóm tắt/đạo đức cao hơn tội phạm (9/22).
- Câu 1 ngắn (~15 từ), có thể bắt đầu bằng phản ứng: "No, no, no." / "Someone needs to save Jr." / "We have some breaking news regarding legendary musician Lionel Richie. No, he is not dead, but he is currently in the ICU." (749K) / "People want it for your rest or? Heather Wyatt has posted a statement ..." (1,4M) / "According to breaking news reports ... the comedian Carrot Top was reportedly hospitalized..."
- Thân: trích lời người trong cuộc ("X wrote, ...") rồi bình luận ngôi thứ nhất.
- Kết thật: "So hopefully that's all we're dealing with here." / "So I wanted to come on and give you guys that update in case you haven't seen it." / "Kashan rock Obviously knew she was pregnant... Why would you even try to do that?" (kết bằng câu hỏi giận dữ, hiếm).
- Prompt (EN):
```
Write a 62-68 second American-English narration, conversational gossip-news tone, about 200 words. Open with a 5-12 word reaction or teaser ("No, not dead. But in the ICU.") then the named person and the new development. Sentences avg 15-17 words. Quote the person's own statement in one or two short lines ("She wrote, ..."), attribute everything else ("reportedly", "according to TMZ"). Give one sympathy beat and one curiosity gap before the end. Final sentence: a doubtful question ending on the open question, such as "So is this really the full story?" Do not trail off; the question is the last sentence.
```

## 3. Trend/viral (n=3 — chỉ giai thoại)
Mẫu: Sydney Till tử vong (71,8K) mở bằng "Tiktok star ... has passed away age 26 following a three-year battle..."; Emilie Kiser (40K) mở "After weeks of backlash, influencer ... has finally spoken out..." rồi "The clip quickly went viral with many social media users questioning..." Kết thật: "He was only three years old and should have lived a lifetime more." (thương tâm). Prompt: cùng khung scandal, câu 2 bắt buộc nêu quy mô lan truyền ("went viral", số người xem/theo dõi) và phản ứng dư luận; kết câu hỏi nghi vấn về động cơ/thực hư. Không rút luật số từ n=3.

## 4. Hồ sơ cũ (n=4 — chỉ giai thoại)
Mẫu: "The youngest woman to be sentenced to death in the United States will be executed next week for the torture and murder of her 19-year-old classmate. In the fall of 1994, ..." (32,7K): câu 1 là mốc hiện tại (sắp hành quyết), câu 2 quay lại năm cũ rồi kể tuần tự. Tốc độ cao nhất (~212 wpm). Prompt: "Open with the present-day trigger (verdict, execution, reopened case) in one sentence, then 'In [year], ...' chronology, close with the unresolved doubt as a question."

## 5. Cái chết/sức khoẻ người nổi tiếng (n=14; trung vị 7.979; viral 36%)
Đo: 191 từ, câu 17,7 từ, tone grief 8/14, style third_person_news 8; 7/14 kết tóm tắt/tri ân; 0/14 kết bằng câu hỏi; wpm chậm nhất (186), nhiều khoảng ngắt nhất (3,05 ngắt >0,3 s/phút; grief 5,0).
- Câu 1: tin trực tiếp, ngắn ~8-12 từ: "Liam Fitzgerald has tragically passed away." / "Legendary voice actor Mike McFarlane has passed away." / "No, no, no. Karla Jeffrey, star of Disney's popular Zombies franchise, has recently passed away at the age of 33." (412K) / "AEW has announced the passing of celebrated professional wrestler Benjamin Satterley..." (196K).
- Kết thật: "Rest in peace, Mike McFarlane." / "Numerous fans and industry peers have posted tributes online..." / "She would have been turning 37."
- Prompt (EN):
```
Write a 60-66 second American-English obituary-news narration, ~185 words, slow, soft and respectful. Sentence 1 (<=12 words): the death announcement with name and role. Sentence 2: age, cause or circumstances if confirmed by the family or an official statement, with source in 3-5 words. Body: career highlights then reactions and tributes, short sentences. Never speculate about cause unless attributed. Final two sentences: a tribute line, then ONE gentle open question that casts doubt or longing without accusing anyone ("Why did the signs go unnoticed?" / "Who will carry that voice now?"). End on the question.
```

## Luật câu kết nghi vấn (áp mọi nhóm)
1. Câu hỏi là câu CUỐI CÙNG (không thêm câu sau), tối đa 14 từ, nêu nghi vấn thay vì khẳng định, không buộc tội người thật bằng câu hỏi.
2. Ngay trước đó là một nhịp cảm xúc (thương tâm/đồng cảm: nhóm có trung vị cao nhất) để tránh tụt cảm xúc; không được kết bằng câu giải thích hay CTA nhẹ sau câu hỏi.
3. Không kết lửng giữa câu (kênh có 16/83 video bị cắt, coi là lỗi).
4. Đo bằng kiểm tra tự động: câu cuối kết thúc bằng "?", có động từ, ≤14 từ, không chứa "allegedly is guilty"/khẳng định tội.
5. Khuyến nghị thử A/B vì dữ liệu kênh KHÔNG chứng minh câu hỏi cuối tăng lượt xem (n=2).
