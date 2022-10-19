import json


with open(
    os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-web-info.json",
    "r",
) as json_file:  # Keeps track of the actions taken by parser job
    json_object = json.load(json_file)

with open(
    os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-retry-info.json",
    "r",
) as json_file:  # Keeps track of the links to the retry job
    json_retry_object = json.load(json_file)

with open(
    os.environ.get("HOME")
    + "/builds/jenkins-test-parser-monitor/test-parser-web-info.html",
    "w",
) as html_file:  # Static web page

    head = '<!DOCTYPE html>\n\
<html>\n\
   <head>\n\
      <meta name="viewport" content="width=device-width, initial-scale=1">\n\
      <style>\n\
         * {\n\
         box-sizing: border-box;\n\
         }\n\
         #SearchBar {\n\
         width: 95%;\n\
         margin-left: 35px;\n\
         font-size: 16px;\n\
         padding: 12px 20px 12px 40px;\n\
         border: 1px solid #ddd;\n\
         margin-bottom: 12px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         h1 {\n\
         margin-left: 40px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         p {\n\
         margin-left: 40px;\n\
         margin-bottom: 12px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Table {\n\
         border-collapse: collapse;\n\
         width: 95%;\n\
         border: 1px solid #ddd;\n\
         margin-left: 35px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Table th {\n\
         text-align: left;\n\
         padding: 12px;\n\
         font-size: 18px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Table tr.header {\n\
         background-color: #f1f1f1;\n\
         font-size: 20px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Table tr {\n\
         border-bottom: 1px solid #ddd;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .NoAction td {\n\
         background-color: #dba398;\n\
         text-align: left;\n\
         padding: 12px;\n\
         font-size: 16px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Retry td {\n\
         text-align: left;\n\
         padding: 12px;\n\
         font-size: 16px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
         .Table tr:hover {\n\
         background-color: #f1f1f1;\n\
         font-size: 20px;\n\
         font-family: Arial, sans-serif;\n\
         }\n\
      </style>\n\
   </head>\n\
   <body>\n\
      <h1>Jenkins parser monitor</h1>\n\
      <p>The table below displays the activity of the <a href="https://cmssdt.cern.ch/jenkins/job/jenkins-test-parser/">Jenkins Parser job</a>.</p>\n\
      <p>Red entries correspond to failed jobs where the Jenkins Parser has not taken any action. Please, take the appropiate action in those cases. White entries correspond to jobs retried by the Parser because a known Error Message was found in the log.</p>\n\
      <input type="text" id="SearchBar" onkeyup="myFunction()" placeholder="Filter by job name ..." title="Type job name">\n\
      <table id="Table" class="Table">\n\
         <tr class="header">\n\
            <th>Time</th>\n\
            <th>Job Name</th>\n\
            <th>Build Number</th>\n\
            <th>Error Message</th>\n\
            <th>Link to failed build</th>\n\
            <th>Link to retry job</th>\n\
         </tr>\n\
         </tr>\n\
         </thead>\n\
         <tbody>\n'

    html_file.write(head)

    for id in reversed(list(json_object["parserActions"].keys())):
        table_entries = list(json_object["parserActions"][id].keys())
        # Remove html class entry
        table_entries.pop()

        action = json_object["parserActions"][id]["parserAction"]
        html_file.writelines('   <tr class="' + action + '">\n')

        job_to_retry = json_object["parserActions"][id]["jobName"]
        build_to_retry = json_object["parserActions"][id]["buildNumber"]

        try:
            retry_url = json_retry_object["retryUrl"][job_to_retry][build_to_retry]
        except Exception:
            retry_url = ""
            print("Retry url not present for " + job_to_retry + " #" + build_to_retry)

        if action == "NoAction":
            for item in table_entries:
                if item == "failedBuild":
                    html_file.writelines(
                        '      <td><a href="'
                        + json_object["parserActions"][id][item]
                        + '">'
                        + json_object["parserActions"][id][item]
                        + "</a></td>\n"
                    )
                else:
                    html_file.writelines(
                        "      <td>"
                        + json_object["parserActions"][id][item]
                        + "</td>\n"
                    )

        elif action == "Retry":
            for item in table_entries:
                if item == "failedBuild":
                    html_file.writelines(
                        '      <td><a href="'
                        + json_object["parserActions"][id][item]
                        + '">'
                        + json_object["parserActions"][id][item]
                        + "</a></td>\n"
                    )
                elif item == "retryJob" and retry_url != "":
                    html_file.writelines(
                        '      <td><a href="'
                        + retry_url
                        + '">'
                        + retry_url
                        + "</a></td>\n"
                    )
                else:
                    html_file.writelines(
                        "      <td>"
                        + json_object["parserActions"][id][item]
                        + "</td>\n"
                    )

        html_file.writelines("   </tr>\n")

    tail = '   </table>\n\
      <script>\n\
         function myFunction() {\n\
           var input, filter, table, tr, td, i, txtValue;\n\
           input = document.getElementById("SearchBar");\n\
           filter = input.value.toUpperCase();\n\
           table = document.getElementById("Table");\n\
           tr = table.getElementsByTagName("tr");\n\
           for (i = 0; i < tr.length; i++) {\n\
             td = tr[i].getElementsByTagName("td")[1];\n\
             if (td) {\n\
               txtValue = td.textContent || td.innerText;\n\
               if (txtValue.toUpperCase().indexOf(filter) > -1) {\n\
                 tr[i].style.display = "";\n\
               } else {\n\
                 tr[i].style.display = "none";\n\
               }\n\
             }\n\
           }\n\
         }\n\
      </script>\n\
   </body>\n\
</html>\n'

    html_file.write(tail)
