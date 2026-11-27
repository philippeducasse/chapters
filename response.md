# A3. Reply to the admin

Write a short reply to the admin who sent the ticket, half a page at most. The admin is not a developer.
Explain what caused the problem, what you changed, and what the admin can check or do themselves next
time.

Hi admin,

Thanks for the message and getting in touch. I found the root cause of the problem, and it's because four
of the invoices in the knowledge base were scans (and therefore images), which resulted in the agent not
being able to read them correctly. I fixed the issue by allowing images containing text to also be processed,
so you don't have to change anything, but please check the following:

1. Ask the agent to find the invoice RE-2026-0417, it should now retrieve it correctly.
2. Type in $Supplier Invoice Total in the prompt, followed by the company name, it calculates the sum more reliably. For nordlicht, that's 14.065,80 (14.351,40 income, minus a credit of -285,60 from GS-2026-0021)

Having the invoices as text in the pdf is more reliable, and I would encourage you to try to avoid scans. The images are sometimes blurry / difficult for the agent to read, making them generally less reliable.

Let me know if you encounter any other issues.

Best,
Philippe
