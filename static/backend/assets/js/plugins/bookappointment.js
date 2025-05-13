/*
Version: 1.3.0
Template: Xray Clinic And Patient Management Dashboard
Author: iqonic.design
Design and Developed by: iqonic.design
NOTE: This file contains the all calender events.
*/
"use strict"
const addelem = document.getElementById('add-appointment');
const addbutton = addelem.querySelector('[name="save"]');
addbutton.addEventListener('click', addappointment);
var bookingcalendar
function addappointment() {
    var services = Array.from(addelem.querySelector('[name="service"]').options).filter(option => option.selected).map(option => option.value);
    var adddata = {
        title: addelem.querySelector('#addtitle').value,
        drname: addelem.querySelector('#addname').value,
        start: addelem.querySelector('[name="start_date"]').value + 'T05:30:00.000Z',
        end: addelem.querySelector('[name="end_date"]').value + 'T05:30:00.000Z',
        starttime: addelem.querySelector('[name="start_time"]').value,
        endtime: addelem.querySelector('[name="end_time"]').value,
        desc: addelem.querySelector('[name="description"]').value,
        checked: addelem.querySelector('#addconfirm2').checked,
        service: services,
        backgroundColor: 'rgba(58,87,232,0.2)',
        textColor: 'rgba(58,87,232,1)',
        borderColor: 'rgba(58,87,232,1)',
    };
    bookingcalendar.addEvent(adddata)
    addelem.querySelector('#add-form').reset()
    addelem.querySelector('#addconfirm2').checked = false
};
if (document.querySelectorAll('#bookingcalendar').length) {
    document.addEventListener('DOMContentLoaded', function () {
        let calendarEl = document.getElementById('bookingcalendar');
        bookingcalendar = new FullCalendar.Calendar(calendarEl, {
            selectable: true,
            plugins: ["timeGrid", "dayGrid", "list", "interaction"],
            timeZone: "UTC",
            defaultView: "dayGridMonth",
            contentHeight: "auto",
            eventLimit: true,
            dayMaxEvents: 4,
            header: {
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,timeGridWeek,timeGridDay"
            },
            dateClick: function (info) {
                $('#schedule-start-date').val(info.dateStr)
                $('#schedule-end-date').val(info.dateStr)
                $('#date-event').modal('show')
            },
            eventClick: function (info) {
                $('#edit-appointment').modal('show');

                const editelem = document.getElementById('edit-appointment');
                editelem.querySelector('#title-drop-1').value = info.event.title
                editelem.querySelector('#dr-name-1').value = info.event.extendedProps.drname
                editelem.querySelector('[name="start_date"]').value = info.event.start
                editelem.querySelector('[name="end_date"]').value = info.event.end || info.event.start
                editelem.querySelector('[name="start_time"]').value = info.event.extendedProps.starttime || 'enter time'
                editelem.querySelector('[name="end_time"]').value = info.event.extendedProps.endtime || 'enter time'
                editelem.querySelector('[name="description"]').value = info.event.extendedProps.desc || 'provide description'
                editelem.querySelector('#editconfirm').checked = info.event.extendedProps.checked
                var selectoptions = info.event.extendedProps.service
                var selectelem = editelem.querySelector('[name="service"]')
                if (selectoptions) {
                    window.choise.destroy()
                    Array.from(selectelem.options).map(option => {
                        selectoptions.map(opt => {
                            if (option.value == opt) {
                                option.remove()
                            }
                        })
                    })
                    new Choices(selectelem, {
                        editItems: true,
                        removeItemButton: true,
                    }).setValue(selectoptions);
                }
                const updatebutton = editelem.querySelector('[name="save"]');
                updatebutton.addEventListener('click', function () {
                    info.event.setProp('title', editelem.querySelector('#title-drop-1').value);
                });

            },
            eventRender: function (info) {

                var eventElement = info.el;
                var drname = info.event.extendedProps.drname;

                let $eventTime = document.createElement('div')
                $eventTime.classList.add("fc-content");

                let $time = document.createElement('span');
                $time.classList.add("fc-time", "text-uppercase");
                $time.append(eventElement.querySelector(".fc-time").textContent);
                $eventTime.append($time);

                let $evetDetail = document.createElement('span')
                $evetDetail.classList.add("fc-detail")

                // Create the h6 tag
                let $title = document.createElement('h6');
                $title.classList.add("fc-title");
                $title.append(eventElement.querySelector(".fc-title").textContent);

                // Append the h6 tag to $evetDetail
                $evetDetail.append($title);


                // Create an element to hold the extra text
                var eventExtraProsDrName = document.createElement('div');
                eventExtraProsDrName.classList.add('dr-name', 'text-body');
                eventExtraProsDrName.textContent = drname;

                $evetDetail.append(eventExtraProsDrName)

                eventElement.replaceChildren($eventTime, $evetDetail);

            },
            events: [
                {
                    title: 'Regular Checkup',
                    start: moment(new Date(), 'YYYY-MM-DD').add(-22, 'days').format('YYYY-MM-DD') + 'T05:30:00.000Z',
                    backgroundColor: 'rgba(var(--bs-primary-rgb), 0.1)',
                    textColor: 'var(--bs-primary)',
                    borderColor: 'var(--bs-primary)',
                },
                {
                    title: 'Skin Treatment',
                    start: moment(new Date(), 'YYYY-MM-DD').add(-6, 'days').format('YYYY-MM-DD') + 'T05:30:00.000Z',
                    backgroundColor: 'rgba(var(--bs-primary-rgb), 0.1)',
                    textColor: 'var(--bs-primary)',
                    borderColor: 'var(--bs-primary)'
                },
                {
                    title: 'Cardiologist',
                    start: moment(new Date(), 'YYYY-MM-DD').add(-1, 'days').format('YYYY-MM-DD') + 'T05:30:00.000Z',
                    backgroundColor: 'rgba(var(--bs-primary-rgb), 0.1)',
                    textColor: 'var(--bs-primary)',
                    borderColor: 'var(--bs-primary)'
                },
                {
                    title: 'Dentist',
                    start: moment(new Date(), 'YYYY-MM-DD').add(4, 'days').format('YYYY-MM-DD') + 'T05:30:00.000Z',
                    backgroundColor: 'rgba(var(--bs-primary-rgb), 0.1)',
                    textColor: 'var(--bs-primary)',
                    borderColor: 'var(--bs-primary)'
                },
                {
                    title: 'Dentist',
                    start: moment(new Date(), 'YYYY-MM-DD').add(19, 'days').format('YYYY-MM-DD') + 'T05:30:00.000Z',
                    backgroundColor: 'rgba(var(--bs-primary-rgb), 0.1)',
                    textColor: 'var(--bs-primary)',
                    borderColor: 'var(--bs-primary)'
                },
            ]
        });
        bookingcalendar.render();
    });

}
