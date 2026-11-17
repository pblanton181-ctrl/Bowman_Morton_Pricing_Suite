import re 
p = r"C:\Bowman_Morton_Pricing_Suite\live_test.py" 
with open(p, "r", encoding="utf-8") as f: code = f.read() 
        if not self.data_core.rfq_ledger_items: return 
        try: 
            body_lines = ["Bowman-Morton Structural Quoting Breakdown Matrix:\n\n"] 
            tot = 0.0 
            for item in self.data_core.rfq_ledger_items: 
                body_lines.append(f"- {item['model']}: {item['cost']}\n") 
                tot += float(item['cost'].replace("$", "")) 
            body_lines.append(f"\nTotal Order Estimation Summary Value: ${tot:.2f}") 
            body_str = "".join(body_lines) 
            mail_url = f"mailto:?subject=Bowman-Morton%20Manufacturing%20Quote%20Package&body={urllib.parse.quote(body_str)}" 
            if sys.platform == "win32": os.startfile(mail_url) 
code = re.sub(r"def trigger_email_client_package\(self\):.*?except Exception: pass", email_func, code, flags=re.DOTALL) 
code = re.sub(r"(def show_admin_gateway\(self\):.*?){2,}", r"\1", code, flags=re.DOTALL) 
with open(p, "w", encoding="utf-8") as f: f.write(code) 
print("--- PATCH FILE REGISTERED SUCCESSFUL ---") 
