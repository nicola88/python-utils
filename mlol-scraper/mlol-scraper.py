"""
Selenium vs requests scraping
https://milano.medialibrary.it/commons/QueuePos.aspx?id=1807109
"""
import json
import os
import re
import sys
import time

from collections import namedtuple
from datetime import date, datetime, timedelta
from math import floor
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import invisibility_of_element
from typing import List


Reservation = namedtuple('Reservation', ('title', 'authors', 'queue_position', 'available_copies'))
Loan = namedtuple('Loan', ('title', 'authors', 'start_date', 'end_date'))


def close_dialogs(driver):
  wait=WebDriverWait(driver,5)
  try:
    dialogs = driver.find_elements_by_css_selector('.modal-dialog')
    for diag in dialogs:
      diag.find_element_by_css_selector('button[data-dismiss="modal"]').click()
      wait.until(invisibility_of_element(diag))
  except Exception as e:
    print(e)

def login(driver, base_url):
  driver.get(base_url)
  # Accept cookie policy
  driver.find_element_by_css_selector('a[onclick="acceptCookies()"]').click()
  # Fill username field
  username_field = driver.find_element_by_id("lusername")
  username_field.clear()
  username_field.send_keys(config['user.name'])
  # Fill password field
  password_field = driver.find_element_by_id("lpassword")
  password_field.clear()
  password_field.send_keys(config['user.password'])
  # Submit form
  driver.find_element_by_css_selector("#btnLogin > input").click()

def get_active_loans(driver, base_url):
  if base_url[-1] == "/":
    base_url = base_url[:-1]
  driver.get(base_url + "/user/risorse.aspx#mlolloan")
  driver.find_element_by_css_selector('a[href="#mlolloan"]').click()
  active_loans = []
  for entry in driver.find_elements_by_css_selector("#mlolloan .bottom-buffer"):
    book_title = entry.find_element_by_css_selector("h3").text
    book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
    loan_start = entry.find_element_by_css_selector('table tr:first-of-type td:nth-child(2) b').text
    loan_end = entry.find_element_by_css_selector('table tr:nth-child(2) td:nth-child(2) b').text
    active_loans.append(Loan(book_title, book_authors, datetime.strptime(loan_start, '%d/%m/%Y'), datetime.strptime(loan_end, '%d/%m/%Y')))
  return active_loans

def get_reservations(driver, base_url) -> List[Reservation]:
  # Remove trailing slash character from base url - if present - before concatenating with relative URL of reservation page
  if base_url[-1] == "/":
    base_url = base_url[:-1]
  driver.get(base_url + "/user/risorse.aspx#mlolreservation")
  driver.find_element_by_css_selector('a[href="#mlolreservation"]').click()
  reservations = []
  for entry in driver.find_elements_by_css_selector("#mlolreservation .bottom-buffer"):
    book_title = entry.find_element_by_css_selector("h3").text
    book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
    entry.find_element_by_css_selector('div[id^="divPos"] .btn').click()
    queue = entry.find_element_by_css_selector('div[id^="divPos"]')
    print(queue.text)
    queue_position_msg, available_copies_msg = queue.text.split("\n")
    queue_position = QUANTITY_REGEX.match(queue_position_msg).group()
    available_copies = QUANTITY_REGEX.match(available_copies_msg).group()
    reservations.append(Reservation(book_title, book_authors, int(queue_position), int(available_copies)))
  return reservations

def get_all_loans(driver, base_url):
  # Remove trailing slash character from base url - if present - before concatenating with relative URL of reservation page
  if base_url[-1] == "/":
    base_url = base_url[:-1]
  driver.get(base_url + "/user/risorse.aspx#mlolloanhistory")
  driver.find_element_by_css_selector('a[href="#mlolloanhistory"]').click()
  loans = []
  for entry in driver.find_elements_by_css_selector("#mlolloanhistory .bottom-buffer"):
    book_title = entry.find_element_by_css_selector("h3").text
    book_authors = entry.find_element_by_css_selector('span[itemprop="author"]').text
    loan_start = entry.find_element_by_css_selector('table tr:first-of-type td:nth-child(2) b').text
    loan_end = entry.find_element_by_css_selector('table tr:nth-child(2) td:nth-child(2) b').text
    loans.append(Loan(book_title, book_authors, datetime.strptime(loan_start, '%d/%m/%Y'), datetime.strptime(loan_end, '%d/%m/%Y')))
  return loans

def get_favourites():
  pass

def get_book_details():
  pass

def search_books(driver, query: str):
  pass


assert len(sys.argv) == 2, "Missing argument for configuration file"
config_path = os.path.abspath(sys.argv[1])
assert os.path.isfile(config_path), "Configuration file not found or accessible"
config = json.load(open(config_path))

CURRENT_MONTH = date.today().month
CURRENT_YEAR = date.today().year
QUANTITY_REGEX = re.compile('\d+')
MAX_CONCURRENT_RESERVATIONS = config['reservations.max_concurrent']
MAX_MONTHLY_LOANS = config['loans.max_monthly']
BORROW_DURATION_IN_DAYS = config['loans.duration_in_days']

driver = webdriver.Firefox()

login(driver, config['url'])

close_dialogs(driver)

print("ACTIVE LOANS")
active_loans = get_active_loans(driver, config['url'])
for loan in active_loans:
  print(loan)

print("ALL LOANS")
all_loans = get_all_loans(driver, config['url'])
for loan in all_loans:
  print(loan)

current_month_loans = list(filter(lambda l: l.start_date.month == CURRENT_MONTH and l.start_date.year == CURRENT_YEAR, all_loans))
print(f"Found {len(current_month_loans)}/{MAX_MONTHLY_LOANS} loans this month")
if len(current_month_loans) < MAX_MONTHLY_LOANS:
  print(f"Hint: you still have {MAX_MONTHLY_LOANS - len(current_month_loans)} loans(s) available this month")

print("RESERVATIONS")
reservations = get_reservations(driver, config['url'])
for r in reservations:
  print(r)

print(f"Found {len(reservations)}/{MAX_CONCURRENT_RESERVATIONS} reservations")
if len(reservations) < MAX_CONCURRENT_RESERVATIONS:
  print(f"Hint: you still have {MAX_CONCURRENT_RESERVATIONS - len(reservations)} reservation(s) available")

for reservation in reservations:
  people_ahead_in_queue = reservation.queue_position - 1
  rounds_to_wait = floor(people_ahead_in_queue / reservation.available_copies)
  # Best scenario: tomorrow all copies will be available for the next people in the queue
  days_to_wait = 1 + rounds_to_wait * BORROW_DURATION_IN_DAYS
  best_availability = date.today() + timedelta(days=1) + timedelta(days=days_to_wait)
  # Worst scenario: all copies were taken today and they will be available for the next people in the queue after this "round"
  days_to_wait = (rounds_to_wait + 1) * BORROW_DURATION_IN_DAYS
  worst_availability = date.today() + timedelta(days=1) + timedelta(days=days_to_wait)
  print(f"'{reservation.title}' by '{reservation.authors}' should be available between {best_availability} and {worst_availability}")

driver.close()