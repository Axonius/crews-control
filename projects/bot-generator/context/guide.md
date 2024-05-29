# Detailed Explanation for Generating `execution.yaml` Files

This document provides a detailed explanation of how to structure an `execution.yaml` file. This explanation is intended to help a Large Language Model (LLM) understand the components and the format required to generate such files correctly.

## Structure of `execution.yaml`

An `execution.yaml` file consists of several sections: `settings`, `user_inputs` (optional), and `crews`. Below, each section is explained in detail.

### 1. Settings

The `settings` section contains global settings for the execution process. It is a required section.

```
settings:
  output_results: true
```

- **output_results**: A boolean value indicating whether the output results should be generated.

### 2. User Inputs (Optional)

The `user_inputs` section defines inputs that users must provide. This section is optional.

```
user_inputs:
  company_name:
    title: "Company name"
  company_description:
    title: "Company description"
  company_domain:
    title: "Company domain"
  hiring_needs:
    title: "Hiring needs"
  specific_benefits:
    title: "Specific benefits"
```

- **user_inputs**: An object where each key is an input identifier, and its value is an object with a `title` property.
  - **title**: A string that specifies the title of the input.

### 3. Crews

The `crews` section defines the various crews involved in the execution process. Each crew can have multiple agents and tasks. This section is required.

#### Crew Structure

```
crews:
  industry_analysis_crew:
    output_naming_template: '{company_name}-industry-analysis-report.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      industry_analysis_task:
        agent: research_agent
        description: >
          IMPORTANT INSTRUCTIONS:
          -----------------------
          - The following is *NEVER* okay to do: "Action: None", "Action Input: None".
          - If you should provide a final answer, you *MUST* follow the correct "Thought: I now can give a great answer",
           "Final Answer:" format.

          Conduct an in-depth analysis of the industry related to the company's domain: "{company_domain}".

          Investigate current trends, challenges, and opportunities within the industry, utilizing market
          reports, recent developments, and expert opinions.

          Assess how these factors could impact the role being hired for and the overall attractiveness of
          the position to potential candidates.

          Consider how the company's position within this industry and its response to these trends could
          be leveraged to attract top talent.

          Include in your report how the role contributes to addressing industry challenges or seizing
          opportunities.
        expected_output: >
          A detailed analysis report that identifies major industry trends, challenges, and opportunities
          relevant to the company's domain and the specific job role.

          This report should provide strategic insights on positioning the job role and the company as an
          attractive choice for potential candidates.

  research_company_culture_crew:
    output_naming_template: '{company_name}-company-culture-report.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      research_company_culture_task:
        agent: research_agent
        description: >
          Analyze the provided company website and the hiring manager's company's domain {company_domain},
          description: "{company_description}".
          Focus on understanding the company's culture, values, and mission.

          Identify unique selling points and specific projects or achievements highlighted on the site.
          Compile a report summarizing these insights, specifically how they can be leveraged in a job
          posting to attract the right candidates.
        expected_output: >
          A comprehensive report detailing the company's culture, values, and mission, along with specific
          selling points relevant to the job role. Suggestions on incorporating these insights into the job
          posting should be included.

  research_role_requirements_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-role-requirements-list.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      research_role_requirements_task:
        agent: research_agent
        description: >
          Based on the hiring manager's needs: "{sha256:hiring_needs}", identify the key skills, experiences, and
          qualities the ideal candidate should possess for the role.

          Consider the company's current projects,
          its competitive landscape, and industry trends.

          Prepare a list of recommended job requirements and
          qualifications that align with the company's needs and values.
        expected_output: >
          A list of recommended skills, experiences, and qualities for the ideal candidate, aligned with the
          company's culture, ongoing projects, and the specific role's requirements.

  draft_job_posting_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-draft-job-posting.md'
    agents:
      writer_agent:
        role: "Job Description Writer"
        goal: >
          Use insights from the Research Analyst to create a detailed, engaging, and enticing job posting.
        tools:
          - serper
          - website_search
          - read_file
        backstory: >
          Skilled in crafting job descriptions that attract top talent by highlighting the company's
          unique culture, values, and benefits.
    tasks:
      draft_job_posting_task:
        agent: writer_agent
        description: >
          Draft a job posting for the role described by the hiring manager: "{hiring_needs}".

          Use the insights on "{company_description}" to start with a compelling introduction, followed by a
          detailed role description, responsibilities, and required skills and qualifications.

          Ensure the tone aligns with the company's culture and incorporate any unique benefits or
          opportunities offered by the company.
          
          Specific benefits: "{specific_benefits}"
        expected_output: >
          A detailed, engaging job posting that includes an introduction, role description, responsibilities,
          requirements, and unique company benefits.

          The tone should resonate with the company's culture and values,
          aimed at attracting the right candidates.

  review_and_edit_job_posting_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-final-job-posting.md'
    agents:
      review_agent:
        role: "Review and Editing Specialist"
        goal: >
          Review the job posting for clarity, engagement, grammatical accuracy, and alignment with company
          values and refine it to ensure perfection.
        tools:
          - serper
          - website_search
          - read_file
        backstory: >
          A meticulous editor with an eye for detail, ensuring every piece of content is clear, engaging,
          and grammatically perfect.
    tasks:
      review_and_edit_job_posting_task:
        agent: review_agent
        description: >
          Review the draft job posting for the role: "{hiring_needs}".
          
          Check for clarity, engagement, grammatical accuracy, and alignment with the company's culture and
          values.
          
          Edit and refine the content, ensuring it speaks directly to the desired candidates and accurately
          reflects the role's unique benefits and opportunities.
          
          Provide feedback for any necessary revisions.
        expected_output: >
          A polished, error-free job posting that is clear, engaging, and perfectly aligned with the
          company's culture and values.
          
          Feedback on potential improvements and final approval for publishing.
          
          Formatted in markdown.
```

### Explanation

- **output_naming_template**: A template string for naming the output file, using placeholders for dynamic values. If a placeholder has a `sha256:` prefix, it indicates that the value should be replaced with the SHA-256 hex digest of the content of the variable.
- **context**: (Optional) An object with key/value pairs where keys are used in templating syntax and values are filenames. These files reside inside the context subfolder, and their content will be inlined using the templating syntax.
- **agents**: An object where each key is an agent identifier, and its value is an object with the agent's details.
  - **role**: The role of the agent.
  - **goal**: The goal of the agent.
  - **backstory**: A description of the agent's background.
  - **tools**: A list of tools available to the agent.
- **tasks**: An object where each key is a task identifier, and its value is an object with the task's details.
  - **agent**: The agent responsible for the task.
  - **description**: A detailed description of the task.
  - **expected_output**: The expected output of the task.

### Example of an `execution.yaml` File

Here is a complete example of an `execution.yaml` file:

```
settings:
  output_results: true

user_inputs:
  company_name:
    title: "Company name"
  company_description:
    title: "Company description"
  company_domain:
    title: "Company domain"
  hiring_needs:
    title: "Hiring needs"
  specific_benefits:
    title: "Specific benefits"

crews:
  industry_analysis_crew:
    output_naming_template: '{company_name}-industry-analysis-report.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      industry_analysis_task:
        agent: research_agent
        description: >
          IMPORTANT INSTRUCTIONS:
          -----------------------
          - The following is *NEVER* okay to do: "Action: None", "Action Input: None".
          - If you should provide a final answer, you *MUST* follow the correct "Thought: I now can give a great answer",
           "Final Answer:" format.

          Conduct an in-depth analysis of the industry related to the company's domain: "{company_domain}".

          Investigate current trends, challenges, and opportunities within the industry, utilizing market
          reports, recent developments, and expert opinions.

          Assess how these factors could impact the role being hired for and the overall attractiveness of
          the position to potential candidates.

          Consider how the company's position within this industry and its response to these trends could
          be leveraged to attract top talent.

          Include in your report how the role contributes to addressing industry challenges or seizing
          opportunities.
        expected_output: >
          A detailed analysis report that identifies major industry trends, challenges, and opportunities
          relevant to the company's domain and the specific job role.

          This report should provide strategic insights on positioning the job role and the company as an
          attractive choice for potential candidates.

  research_company_culture_crew:
    output_naming_template: '{company_name}-company-culture-report.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      research_company_culture_task:
        agent: research_agent
        description: >
          Analyze the provided company website and the hiring manager's company's domain {company_domain},
          description: "{company_description}".
          Focus on understanding the company's culture, values, and mission.

          Identify unique selling points and specific projects or achievements highlighted on the site.
          Compile a report summarizing these insights, specifically how they can be leveraged in a job
          posting to attract the right candidates.
        expected_output: >
          A comprehensive report detailing the company's culture, values, and mission, along with specific
          selling points relevant to the job role. Suggestions on incorporating these insights into the job
          posting should be included.

  research_role_requirements_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-role-requirements-list.md'
    agents:
      research_agent:
        role: "Research Analyst"
        goal: >
          Analyze the {company_domain} and provided description to extract insights on culture, values,
          and specific needs.
        tools:
          - website_search
          - serper
        backstory: >
          Expert in analyzing company cultures and identifying key values and needs from various sources,
          including websites and brief descriptions.
    tasks:
      research_role_requirements_task:
        agent: research_agent
        description: >
          Based on the hiring manager's needs: "{sha256:hiring_needs}", identify the key skills, experiences, and
          qualities the ideal candidate should possess for the role.

          Consider the company's current projects,
          its competitive landscape, and industry trends.

          Prepare a list of recommended job requirements and
          qualifications that align with the company's needs and values.
        expected_output: >
          A list of recommended skills, experiences, and qualities for the ideal candidate, aligned with the
          company's culture, ongoing projects, and the specific role's requirements.

  draft_job_posting_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-draft-job-posting.md'
    agents:
      writer_agent:
        role: "Job Description Writer"
        goal: >
          Use insights from the Research Analyst to create a detailed, engaging, and enticing job posting.
        tools:
          - serper
          - website_search
          - read_file
        backstory: >
          Skilled in crafting job descriptions that attract top talent by highlighting the company's
          unique culture, values, and benefits.
    tasks:
      draft_job_posting_task:
        agent: writer_agent
        description: >
          Draft a job posting for the role described by the hiring manager: "{hiring_needs}".

          Use the insights on "{company_description}" to start with a compelling introduction, followed by a
          detailed role description, responsibilities, and required skills and qualifications.

          Ensure the tone aligns with the company's culture and incorporate any unique benefits or
          opportunities offered by the company.
          
          Specific benefits: "{specific_benefits}"
        expected_output: >
          A detailed, engaging job posting that includes an introduction, role description, responsibilities,
          requirements, and unique company benefits.

          The tone should resonate with the company's culture and values,
          aimed at attracting the right candidates.

  review_and_edit_job_posting_crew:
    output_naming_template: '{company_name}-{sha256:hiring_needs}-final-job-posting.md'
    agents:
      review_agent:
        role: "Review and Editing Specialist"
        goal: >
          Review the job posting for clarity, engagement, grammatical accuracy, and alignment with company
          values and refine it to ensure perfection.
        tools:
          - serper
          - website_search
          - read_file
        backstory: >
          A meticulous editor with an eye for detail, ensuring every piece of content is clear, engaging,
          and grammatically perfect.
    tasks:
      review_and_edit_job_posting_task:
        agent: review_agent
        description: >
          Review the draft job posting for the role: "{hiring_needs}".
          
          Check for clarity, engagement, grammatical accuracy, and alignment with the company's culture and
          values.
          
          Edit and refine the content, ensuring it speaks directly to the desired candidates and accurately
          reflects the role's unique benefits and opportunities.
          
          Provide feedback for any necessary revisions.
        expected_output: >
          A polished, error-free job posting that is clear, engaging, and perfectly aligned with the
          company's culture and values.
          
          Feedback on potential improvements and final approval for publishing.
          
          Formatted in markdown.
```
