import folium

m = folium.Map(location=[56.630975, 47.890519], zoom_start=14)

list_location = [[[56.628421, 47.937373], ],
                 [56.642188, 47.902142],
                 [56.634308, 47.844685],
                 [56.646381, 47.841101]]

for mark in list_location:
    folium.Marker(
        location=mark,
        popup='Текст при клике',  # всплывающее окно
        tooltip='Наведи курсор',  # подсказка при наведении
        icon=folium.Icon(color='red', icon='info-sign')  # цвет и иконка
    ).add_to(m)

m.save("map.html")